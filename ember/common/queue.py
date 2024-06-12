
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.enum import *
import amaranth.lib.memory as memory
from amaranth.utils import ceil_log2, exact_log2
from ember.common import *

class CreditInterface(Signature):
    """ Interface used to exchange credit. 

    Members
    =======
    valid:
        This message is valid
    credit:
        The number of credits.

    """
    def __init__(self, width: int):
        super().__init__({
            "valid": Out(1),
            "credit": Out(ceil_log2(width+1)),
        })

class CreditBus(Signature):
    """ Bi-directional interface for exchanging credit. 

    Members
    =======
    req:
        Credit request
    avail:
        Credit availability

    """
    def __init__(self, width: int):
        super().__init__({
            "req":   Out(CreditInterface(width)),
            "avail": In(CreditInterface(width)),
        })

class CreditQueueUpstream(Signature):
    """ Upstream (producer-facing) interface to a :class:`CreditQueue`.

    Members
    =======
    credit:
        Credit information.
    data:
        Requested data being enqueued.

    """

    def __init__(self, width: int, data_layout: Layout):
        super().__init__({
            "credit": Out(CreditBus(width)),
            "data": Out(data_layout).array(width),
        })

class CreditQueueDownstream(Signature):
    """ Downstream (consumer-facing) interface to a :class:`CreditQueue`.

    Members
    =======
    credit:
        Credit bus. 
    data:
        Data available to be dequeued. 

    """
    def __init__(self, width: int, data_layout: Layout):
        super().__init__({
            "credit": Out(CreditBus(width)),
            "data": In(data_layout).array(width),
        })



class CreditQueue(Component):
    """ A FIFO queue with signalling for downstream and upstream availability. 

    .. warning: 
        Again: this is probably unphysical for various reasons? 
        Single-cycle write-to-read latency probably depends on the consumer 
        being able to drive the read credit signals very early in a cycle? 

        
    """
    def __init__(self, depth: int, width: int, data_layout: Layout):
        self.depth = depth
        self.width = width
        self.data_layout = data_layout
        super().__init__(Signature({
            "up": In(CreditQueueUpstream(width, data_layout)),
            "down": Out(CreditQueueDownstream(width, data_layout)),
        }))

    def elaborate(self, platform):
        m = Module()

        # Backing memory
        mem = m.submodules.mem = memory.Memory(
            shape=self.data_layout,
            depth=self.depth,
            init=[],
        )

        # Instantiate read and write ports
        rp = []
        wp = []
        for idx in range(self.width):
            _wp = mem.write_port()
            _rp = mem.read_port(domain='comb')
            wp.append(_wp)
            rp.append(_rp)

        # The number of occupied queue entries
        r_used = Signal(ceil_log2(self.depth+1), init=0)

        # Current number of read credits being sent downstream
        r_rcredit = Signal(ceil_log2(self.width+1), init=0)
        # Current number of write credits being sent upstream
        r_wcredit = Signal(ceil_log2(self.width+1), init=self.width)

        # Pointer to the oldest entry in the queue
        r_rptr  = Signal(exact_log2(self.depth), init=0)
        # Pointer to the newest entry in the queue
        r_wptr  = Signal(exact_log2(self.depth), init=0)

        # Window of pointers to entries that will be sent downstream
        rptr_arr = Array(Signal(exact_log2(self.depth)) for _ in range(self.width))
        # Window of pointers to entries that will be filled from upstream
        wptr_arr = Array(Signal(exact_log2(self.depth)) for _ in range(self.width))

        # Window mask determined by the number of read credits
        rptr_arr_en = Array(Signal() for _ in range(self.width))
        # Window mask determined by the number of write credits
        wptr_arr_en = Array(Signal() for _ in range(self.width))

        # The number of occupied entries on the next cycle
        next_used = Signal(ceil_log2(self.depth+1))
        # The number of free entries on the next cycle
        next_free = Signal(ceil_log2(self.depth+1))

        # The read pointer on the next cycle
        next_rptr = Signal(exact_log2(self.depth))
        # The write pointer on the next cycle
        next_wptr = Signal(exact_log2(self.depth))

        # The number of read credits on the next cycle
        next_rcredit = Signal(ceil_log2(self.width+1))
        # The number of write credits on the next cycle
        next_wcredit = Signal(ceil_log2(self.width+1))

        # The current read request would result in underflow
        rd_underflow = (self.down.credit.req.credit > r_rcredit)
        # The current write request would result in overflow
        wr_overflow  = (self.up.credit.req.credit > r_wcredit)

        # The read pointer will change on the next cycle
        rd_nz = (self.down.credit.req.credit != 0)
        rd_ok = (self.down.credit.req.valid & rd_nz & ~rd_underflow)

        # The write pointer will change on the next cycle
        wr_nz = (self.up.credit.req.credit != 0)
        wr_ok = (self.up.credit.req.valid & wr_nz & ~wr_overflow)

        # The number of entries allocated this cycle
        num_alloc = Mux(wr_ok, self.up.credit.req.credit, 0)
        # The number of entries freed this cycle
        num_freed = Mux(rd_ok, self.down.credit.req.credit, 0)

        # Pointers to entries that will be available to read next cycle
        m.d.comb += [ rptr_arr[idx].eq(r_rptr + idx) for idx in range(self.width) ]
        m.d.comb += [ rptr_arr_en[idx].eq(idx < r_rcredit) for idx in range(self.width) ]

        # Pointers to entries that will be written this cycle
        m.d.comb += [ wptr_arr[idx].eq(r_wptr + idx) for idx in range(self.width) ]
        m.d.comb += [ wptr_arr_en[idx].eq(idx < r_wcredit) for idx in range(self.width) ]

        # Drive outputs
        m.d.comb += [
            self.down.credit.avail.credit.eq(r_rcredit),
            self.up.credit.avail.credit.eq(r_wcredit),
        ]

        # Compute pointers/credits for the next cycle
        m.d.comb += [
            next_used.eq(r_used + num_alloc - num_freed),
            next_free.eq(self.depth - next_used),
            next_wcredit.eq(Mux(next_free > self.width, self.width, next_free)),
            next_rcredit.eq(Mux(next_used > self.width, self.width, next_used)),
            next_rptr.eq(r_rptr + self.down.credit.req.credit),
            next_wptr.eq(r_wptr + self.up.credit.req.credit),
        ]
        m.d.sync += [
            r_wcredit.eq(next_wcredit),
            r_rcredit.eq(next_rcredit),
            r_used.eq(next_used),
        ]

        # Drive inputs to the backing memory device
        for idx in range(self.width):
            m.d.comb += [
                rp[idx].addr.eq(rptr_arr[idx]),
                wp[idx].en.eq(wptr_arr_en[idx]),
                wp[idx].addr.eq(wptr_arr[idx]),
                wp[idx].data.eq(self.up.data[idx]),
            ]

        # Select which data is available on the next cycle.
        next_rd_data = Array(Signal(self.data_layout) for _ in range(self.width))
        with m.If((next_rptr == r_wptr) & wr_ok):
            m.d.comb += [ 
                next_rd_data[idx].eq(Mux(wptr_arr_en[idx], self.up.data[idx], 0))
                for idx in range(self.width)
            ]
        with m.Else():
            m.d.comb += [ 
                next_rd_data[idx].eq(Mux(rptr_arr_en[idx], rp[idx].data, 0))
                for idx in range(self.width)
            ]
        m.d.sync += [
            self.down.data[idx].eq(next_rd_data[idx]) for idx in range(self.width)
        ]


        # When a read is occurring this cycle, increment the read pointer
        with m.If(rd_ok):
            m.d.sync += r_rptr.eq(r_rptr + self.down.credit.req.credit)
        # When a write is occurring this cycle, increment the write pointer
        with m.If(wr_ok):
            m.d.sync += r_wptr.eq(r_wptr + self.up.credit.req.credit)

        return m


class Queue(Component):
    """ A FIFO queue that supports pushing/popping multiple entries.

    The effects of push and pop requests are visible on the next cycle. 

    .. warning::
        This is probably very inefficient and not synthesizable
        (in principle?), but we can worry about that after we have something 
        behaviorally correct. 

    Ports
    =====

    i_pop_size:
        Number of entries being popped/consumed this cycle.
    i_push_size:
        Number of entries being pushed this cycle.
    i_push_data:
        Entry data being pushed this cycle.
    o_data:
        The oldest entries in the queue.
    o_pop_limit:
        Number of valid entries in ``o_data`` that are
        allowed to be popped this cycle. 
    o_push_limit:
        Number of entries in ``i_push_data`` that are
        allowed to be pushed this cycle.
    o_overflow:
        The push request on the previous cycle would have
        caused an overflow condition.
    o_underflow:
        The pop request on the previous cycle would have
        caused an underflow condition.


    Parameters
    ==========
    depth:
        The number of queue entries. 
    width:
        The maximum number of entries that can potentially 
        be enqueued/dequeued in a single cycle.  

    """
    def __init__(self, depth: int, width: int, data_layout: Layout, debug=False):
        self.debug = debug
        self.depth = depth
        self.width = width
        self.data_layout = data_layout
        signature = Signature({
            # Push request
            "i_push_data": In(data_layout).array(width),
            "i_push_size": In(ceil_log2(width+1)),

            # Pop request
            "i_pop_size": In(ceil_log2(width+1)),

            # Output data
            "o_data": Out(data_layout).array(width),

            # Pop limit
            "o_pop_limit": Out(ceil_log2(width+1)),

            # Push limit
            "o_push_limit": Out(ceil_log2(width+1)),

            # Overflow/underflow conditions
            "o_overflow": Out(1),
            "o_underflow": Out(1),

            # Number of entries currently in-use
            "o_used": Out(exact_log2(self.depth)),

        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        data_arr = Array(Signal(self.data_layout) for _ in range(self.depth))

        # Registers
        r_rptr = Signal(exact_log2(self.depth), init=0)
        r_wptr = Signal(exact_log2(self.depth), init=0)
        r_used = Signal(ceil_log2(self.depth+1), init=0)
        r_push_limit = Signal(ceil_log2(self.width+1), init=self.width)
        r_pop_limit  = Signal(ceil_log2(self.width+1), init=0)
        r_ovflow = Signal(init=0)
        r_unflow = Signal(init=0)

        next_used = Signal(ceil_log2(self.depth+1))
        next_free = Signal(ceil_log2(self.depth+1))
        next_push_limit = Signal(ceil_log2(self.width+1))
        next_pop_limit  = Signal(ceil_log2(self.width+1))

        push_req = (self.i_push_size != 0)
        pop_req  = (self.i_pop_size != 0)
        ovflow   = (self.i_push_size > r_push_limit)
        unflow   = (self.i_pop_size > r_pop_limit)
        push_ok  = (push_req & ~ovflow)
        pop_ok   = (pop_req & ~unflow)

        # Index/enable wires for accessing the data array
        wptrs      = Array(Signal(exact_log2(self.depth), name=f"wptr{idx}")
                           for idx in range(self.width))
        rptrs      = Array(Signal(exact_log2(self.depth), name=f"rptr{idx}")
                           for idx in range(self.width))
        wptrs_en   = Array(Signal(name=f"wptr{idx}_en")
                           for idx in range(self.width))
        rptrs_en   = Array(Signal(name=f"rptr{idx}_en")
                           for idx in range(self.width))

        # Compute the indexes of the oldest entries in the queue. 
        # Compute the indexes of the newest entries in the queue. 
        m.d.comb += [ wptrs[idx].eq(r_wptr + idx) for idx in range(self.width) ]
        m.d.comb += [ rptrs[idx].eq(r_rptr + idx) for idx in range(self.width) ]
        m.d.comb += [ wptrs_en[idx].eq(idx < r_push_limit) for idx in range(self.width)]
        m.d.comb += [ rptrs_en[idx].eq(idx < r_pop_limit) for idx in range(self.width)]

        # Connect registers to the outputs
        m.d.comb += [
            self.o_push_limit.eq(r_push_limit),
            self.o_pop_limit.eq(r_pop_limit),
            self.o_used.eq(r_used),
            self.o_overflow.eq(r_ovflow),
            self.o_underflow.eq(r_unflow),
        ]

        # Compute the push/pop limits that will be valid on the next cycle
        num_alloc = Mux(push_ok, self.i_push_size, 0)
        num_freed = Mux(pop_ok, self.i_pop_size, 0)
        m.d.comb += [
            next_used.eq(r_used + num_alloc - num_freed),
            next_free.eq(self.depth - next_used),
            next_push_limit.eq(Mux(next_free > self.width, self.width, next_free)),
            next_pop_limit.eq(Mux(next_used > self.width, self.width, next_used)),
        ]

        # Always drive output data from the oldest queue entries.
        # NOTE: These are combinational reads ... is this very unphysical?
        for idx in range(self.width):
            with m.If(rptrs_en[idx]):
                m.d.comb += self.o_data[idx].eq(data_arr[rptrs[idx]])

        # When a push request is valid, capture data and update write pointer
        with m.If(push_ok):
            for idx in range(self.width):
                with m.If(wptrs_en[idx]):
                    m.d.sync += data_arr[wptrs[idx]].eq(self.i_push_data[idx])
            m.d.sync += r_wptr.eq(r_wptr + self.i_push_size)
            m.d.sync += r_used.eq(r_used + self.i_push_size)

        # When a pop request is valid, update read pointer
        with m.If(pop_ok):
            m.d.sync += r_rptr.eq(r_rptr + self.i_pop_size)

        # Update registers with values computed during this cycle
        m.d.sync += [
            r_used.eq(next_used),
            r_push_limit.eq(next_push_limit),
            r_pop_limit.eq(next_pop_limit),
            r_ovflow.eq(ovflow),
            r_unflow.eq(unflow),
        ]


        return m


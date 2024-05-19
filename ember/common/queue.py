
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.enum import *
import amaranth.lib.memory as memory
from amaranth.utils import ceil_log2, exact_log2
from ember.common import *

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


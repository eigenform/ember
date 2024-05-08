
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.enum import *
from amaranth.utils import ceil_log2, exact_log2
from ember.common import *

class Queue(Component):
    """ A FIFO queue that supports pushing/popping multiple entries.

    .. warning::
        This is probably very inefficient and not synthesizable, but we can 
        worry about that after we have something behaviorally correct. 

    - ``i_pop_size``   - Number of entries being popped/consumed this cycle.
    - ``i_push_size``  - Number of entries being pushed this cycle.
    - ``i_push_data``  - Entry data being pushed this cycle.

    - ``o_data``       - The oldest entries in the queue.
    - ``o_pop_limit``  - The number of valid entries in ``o_data`` that are
                         allowed to be popped this cycle. 
    - ``o_push_limit`` - The number of entries in ``i_push_data`` that are 
                         allowed to be pushed this cycle.

    - ``o_overflow``   - The push request on the previous cycle would have 
                         caused an overflow condition.
    - ``o_underflow``  - The pop request on the previous cycle would have 


    Parameters
    ==========
    - The ``depth`` of the queue is the number of entries. 
    - The ``width`` of the queue is the maximum number of entries that can 
      potentially be enqueued/dequeued in a single cycle.  

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
        r_rptr = Signal(exact_log2(self.depth), init=0)
        r_wptr = Signal(exact_log2(self.depth), init=0)
        r_used = Signal(ceil_log2(self.depth+1), init=0)
        r_push_limit = Signal(ceil_log2(self.width+1), init=self.width)
        r_pop_limit  = Signal(ceil_log2(self.width+1), init=0)

        # Index/enable wires for accessing the data array
        wptrs      = Array(Signal(exact_log2(self.depth)) for _ in range(self.width))
        rptrs      = Array(Signal(exact_log2(self.depth)) for _ in range(self.width))
        wptrs_en   = Array(Signal() for _ in range(self.width))
        rptrs_en   = Array(Signal() for _ in range(self.width))

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

        # Compute the indexes used for push/pop operations this cycle
        m.d.comb += [ wptrs[idx].eq(r_wptr + idx) for idx in range(self.width) ]
        m.d.comb += [ rptrs[idx].eq(r_rptr + idx) for idx in range(self.width) ]
        m.d.comb += [ wptrs_en[idx].eq(idx < r_push_limit) for idx in range(self.width)]
        m.d.comb += [ rptrs_en[idx].eq(idx < r_pop_limit) for idx in range(self.width)]

        # Drive outputs from registers
        m.d.comb += [
            self.o_push_limit.eq(r_push_limit),
            self.o_pop_limit.eq(r_pop_limit),
            self.o_used.eq(r_used),
        ]

        num_alloc = Mux(push_ok, self.i_push_size, 0)
        num_freed = Mux(pop_ok, self.i_pop_size, 0)
        m.d.comb += [
            next_used.eq(r_used + num_alloc - num_freed),
            next_free.eq(self.depth - next_used),
            next_push_limit.eq(Mux(next_free > self.width, self.width, next_free)),
            next_pop_limit.eq(Mux(next_used > self.width, self.width, next_used)),
        ]

        for idx in range(self.width):
            with m.If(rptrs_en[idx]):
                m.d.comb += self.o_data[idx].eq(data_arr[rptrs[idx]])

        with m.If(push_ok):
            for idx in range(self.width):
                with m.If(wptrs_en[idx]):
                    m.d.sync += data_arr[wptrs[idx]].eq(self.i_push_data[idx])
            m.d.sync += r_wptr.eq(r_wptr + self.i_push_size)
            m.d.sync += r_used.eq(r_used + self.i_push_size)

        with m.If(pop_ok):
            m.d.sync += r_rptr.eq(r_rptr + self.i_pop_size)

        m.d.sync += [
            r_used.eq(next_used),
            r_push_limit.eq(next_push_limit),
            r_pop_limit.eq(next_pop_limit),
            self.o_overflow.eq(ovflow),
            self.o_underflow.eq(unflow),
        ]


        return m


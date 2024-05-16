from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Signature as WishboneSignature

from ember.common import *
from ember.riscv.paging import *
from ember.param import *
from ember.front.l1i import L1ICacheWritePort
from ember.uarch.fetch import *
from ember.sim.fakeram import *

class L1IFillRequest(Signature):
    """ L1 instruction cache fill request.

    - ``valid``: This request is valid
    - ``addr``: Physical address for this request
    - ``way``: Target way in the L1I cache

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "addr": Out(p.paddr),
            "way": Out(ceil_log2(p.l1i.num_ways)),
            "ftq_idx": Out(FTQIndex(p)),
        })

class L1IFillResponse(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "ftq_idx": Out(FTQIndex(p)),
        })



class L1IFillStatus(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready":  Out(1),
        })

class L1IMshrState(Enum, shape=2):
    # No request is being serviced
    NONE      = 0
    # The request is being serviced by a remote memory device
    ACCESS    = 1
    # The request data is available and being written back to the L1I
    WRITEBACK = 2
    # The request has been completed
    COMPLETE  = 3 


class L1IMissStatusHoldingRegister(Component):
    """ L1I cache "miss-status holding register" (MSHR)

    The L1I fill unit includes MSHRs that are used to track fill requests 
    generated by both demand fetch and prefetch requests that have missed in 
    the L1I cache. An MSHR holds the request while data is being received 
    from memory and written back to the L1I cache data/tag arrays. 

    An MSHR moves through the following sequence of states:

    - ``L1IMshrState.NONE``: Ready to accept a request
    - ``L1IMshrState.ACCESS``: Request is registered and being sent to memory
    - ``L1IMshrState.WRITEBACK``: Response from memory is registered and being
      sent to the IFU and L1I cache write port
    - ``L1IMshrState.COMPLETE``: L1I cache write port response is acknowledged
      and the state of this MSHR is reset

    Upon completion, the L1I fill unit signals the FTQ indicating that the 
    FTQ entry which generated the fill request is eligible to be replayed.

    Ports
    =====

    - ``ready``: High when this MSHR is ready to accept a request
    - ``req``: Incoming fill request to this MSHR
    - ``l1i_wp``: L1I cache write port interface
    - ``fakeram``: Memory interface

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "ready": Out(1),
            "req": In(L1IFillRequest(param)),
            "l1i_wp": Out(L1ICacheWritePort(param)),
            "fakeram": Out(FakeRamInterface()),
        })
        super().__init__(signature)
        return

    def elaborate(self, platform):
        m = Module()

        state   = Signal(L1IMshrState, init=L1IMshrState.NONE)
        addr    = Signal(self.p.paddr)
        way     = Signal(ceil_log2(self.p.l1i.num_ways))
        ftq_idx = Signal(FTQIndex(self.p))
        data    = Signal(self.p.l1i.line_layout)

        with m.Switch(state):
            with m.Case(L1IMshrState.NONE):
                with m.If(self.req.valid):
                    m.d.sync += state.eq(L1IMshrState.ACCESS)
                    m.d.sync += self.ready.eq(0)
                    m.d.sync += addr.eq(self.req.addr)
                    m.d.sync += way.eq(self.req.way)
                    m.d.sync += ftq_idx.eq(self.req.ftq_idx)

            with m.Case(L1IMshrState.ACCESS):
                m.d.comb += [
                    self.fakeram.req.addr.eq(addr),
                    self.fakeram.req.valid.eq(1),
                ]
                with m.If(self.fakeram.resp.valid):
                    m.d.sync += state.eq(L1IMshrState.WRITEBACK)
                    m.d.sync += data.eq(Cat(*self.fakeram.resp.data))

            with m.Case(L1IMshrState.WRITEBACK):
                m.d.comb += [
                    self.l1i_wp.req.valid.eq(1),
                    self.l1i_wp.req.set.eq(addr.l1i.set),
                    self.l1i_wp.req.way.eq(way),
                    self.l1i_wp.req.line_data.eq(data),
                    self.l1i_wp.req.tag_data.ppn.eq(addr.sv32.ppn),
                    self.l1i_wp.req.tag_data.valid.eq(1),
                ]
                with m.If(self.l1i_wp.resp.valid):
                    m.d.sync += state.eq(L1IMshrState.COMPLETE)

            with m.Case(L1IMshrState.COMPLETE):
                m.d.sync += state.eq(L1IMshrState.NONE)
                m.d.sync += self.ready.eq(1)
                pass

        return m


class L1IFillUnit(Component):
    """ Logic for moving bytes from remote memory into the L1I cache.

    The L1I fill unit tracks outstanding cache misses until data has been 
    written back to the L1I data/tag arrays.

    - ``sts``: Fill unit status driven [upstream] to instruction fetch logic
    - ``l1i_wp``: L1I cache write port[s]
    - ``req``: Fill request from instruction fetch logic
    - ``resp``: Response to the FTQ
    - ``fakeram``: Interface[s] to a mock RAM device

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "sts":     Out(L1IFillStatus(param)),
            "l1i_wp":  Out(L1ICacheWritePort(param)),
            "req":      In(L1IFillRequest(param)),
            "resp":    Out(L1IFillResponse(param)),
            "fakeram": Out(FakeRamInterface()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        mshr = []
        for idx in range(self.p.l1i.fill.num_mshr):
            x = m.submodules[f"mshr{idx}"] = L1IMissStatusHoldingRegister(self.p)
            mshr.append(x)

        mshr_ready = Array(
            Signal(name=f"mshr{idx}_ready") 
            for idx in range(self.p.l1i.fill.num_mshr)
        )
        m.d.comb += [
            mshr_ready[idx].eq(mshr[idx].ready)
            for idx in range(self.p.l1i.fill.num_mshr)
        ]

        connect(m, mshr[0].l1i_wp, flipped(self.l1i_wp))
        connect(m, mshr[0].req, flipped(self.req))
        connect(m, mshr[0].fakeram, flipped(self.fakeram))

        #r_addr = Signal(self.p.paddr)
        #r_way  = Signal(ceil_log2(self.p.l1i.num_ways))
        #r_valid = Signal()
        #r_ftq_idx = Signal(FTQIndex(self.p))
        #r_busy = Signal()

        ## Connect registers to fakeram interface
        #m.d.comb += [
        #    self.fakeram.req.valid.eq(r_valid),
        #    self.fakeram.req.addr.eq(r_addr),
        #]
        ## Connect registers to status ports
        ##m.d.comb += [
        ##    self.sts.ready.eq(~r_busy)
        ##]

        ## We can accept a new request when the fakeram interface is free. 
        ## Transaction begins on the next cycle. 
        #req_ok  = (~r_busy & self.req.valid)
        #with m.If(req_ok):
        #    m.d.sync += [
        #        r_addr.eq(self.req.addr),
        #        r_valid.eq(self.req.valid),
        #        r_way.eq(self.req.way),
        #        r_ftq_idx.eq(self.req.ftq_idx),
        #        r_busy.eq(1)
        #    ]


        ## The transaction ends when the fakeram interface signals valid. 
        #result_valid = self.fakeram.resp.valid
        #result_line  = self.fakeram.resp.data

        #resp_ok = (r_busy & result_valid)
        #with m.If(resp_ok):
        #    m.d.sync += [ 
        #        r_busy.eq(0),
        #        r_addr.eq(0),
        #        r_valid.eq(0),
        #        r_way.eq(0),
        #        r_ftq_idx.eq(0),
        #    ]
        #    m.d.comb += [
        #        self.resp.valid.eq(resp_ok),
        #        self.resp.ftq_idx.eq(r_ftq_idx),
        #    ]

        #    m.d.comb += [
        #        self.l1i_wp.req.valid.eq(1),
        #        self.l1i_wp.req.set.eq(r_addr.l1i.set),
        #        self.l1i_wp.req.way.eq(r_way),
        #        self.l1i_wp.req.tag_data.ppn.eq(r_addr.sv32.ppn),
        #        self.l1i_wp.req.tag_data.valid.eq(1),
        #        #self.l1i_wp.req.line_data.eq(result_line),
        #    ]
        #    m.d.comb += [
        #        self.l1i_wp.req.line_data[idx].eq(
        #            self.fakeram.resp.data[idx]
        #        ) for idx in range(self.p.l1i.line_depth)

        #    ]

        return m







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
from ember.cache.l1i import *
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
        })

class L1IFillResponse(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "addr": Out(p.paddr),
        })



class L1IFillStatus(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready":  Out(1),
        })

class L1IFillUnit(Component):
    """ Logic for moving bytes from remote memory into the L1I cache.

    - ``sts``: Fill unit status driven [upstream] to instruction fetch logic
    - ``l1i_wp``: L1I cache write port
    - ``req``: Fill request from instruction fetch logic
    - ``fakeram``: Interface to a mock RAM device

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "sts":     Out(L1IFillStatus(param)),
            "l1i_wp":  Out(L1ICacheWritePort(param)),
            "req":      In(L1IFillRequest(param)),
            "fakeram": Out(FakeRamInterface()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        r_addr = Signal(self.p.paddr)
        r_way  = Signal(ceil_log2(self.p.l1i.num_ways))
        r_valid = Signal()
        r_busy = Signal()

        # Connect registers to fakeram interface
        m.d.comb += [
            self.fakeram.req.valid.eq(r_valid),
            self.fakeram.req.addr.eq(r_addr),
        ]
        # Connect registers to status ports
        m.d.comb += [
            self.sts.ready.eq(~r_busy)
        ]

        # We can accept a new request when the fakeram interface is free. 
        # Transaction begins on the next cycle. 
        req_ok  = (~r_busy & self.req.valid)
        with m.If(req_ok):
            m.d.sync += [
                r_addr.eq(self.req.addr),
                r_valid.eq(self.req.valid),
                r_way.eq(self.req.way),
                r_busy.eq(1)
            ]


        # The transaction ends when the fakeram interface signals valid. 
        result_valid = self.fakeram.resp.valid
        result_line  = self.fakeram.resp.data
        resp_ok = (r_busy & result_valid)
        with m.If(resp_ok):
            m.d.sync += [ 
                r_busy.eq(0),
                r_addr.eq(0),
                r_valid.eq(0),
                r_way.eq(0),
            ]
            m.d.comb += [
                self.l1i_wp.req.valid.eq(1),
                self.l1i_wp.req.set.eq(r_addr.l1i.set),
                self.l1i_wp.req.way.eq(r_way),
                self.l1i_wp.req.tag_data.ppn.eq(r_addr.sv32.ppn),
                self.l1i_wp.req.tag_data.valid.eq(1),
                self.l1i_wp.req.line_data.eq(result_line),
            ]

        return m







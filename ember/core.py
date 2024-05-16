
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth_soc.wishbone import Interface as WishboneInterface

from ember.common import *
from ember.param import *

from ember.front.fetch import *
from ember.decode import *
from ember.front.l1i import *
from ember.front.itlb import *



class EmberCore(Component):

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        m.submodules.l1i = l1i = L1ICache(self.p)
        m.submodules.itlb = itlb = L1ICacheTLB(self.p.l1i)
        m.submodules.l1i_fill = l1i_fill = L1IFillUnit(self.p)
        m.submodules.ifu = ifu = FetchUnit(self.p)

        #fetch_addr = Signal(self.p.rv.xlen, reset=self.p.reset_vector)
        #fetch_addr_v = Signal(reset=True)
        #m.d.sync += addr.eq(addr + 0x20)
        #m.d.comb += [
        #    l1i.fetch_req.valid.eq(1),
        #    l1i.fetch_req.bits.eq(fetch_addr),
        #]
        #m.d.comb += self.bif.addr.eq(addr)

        return m   



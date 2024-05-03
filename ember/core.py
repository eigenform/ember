
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth_soc.wishbone import Interface as WishboneInterface

from ember.common import *
from ember.param import *

from ember.fetch import *
from ember.decode import *
from ember.cache import *



class EmberCore(Component):
    ibus: WishboneInterface(
        addr_width=30, 
        data_width=32, 
        granularity=32, 
        features=["err"]
    )



    def __init__(self, param: EmberParams):
        self.p = param
        super().__init__()

    def elaborate(self, platform):
        m = Module()

        #ifu = m.submodules.ifu = FetchUnit(self.p)
        #fetch_addr = Signal(self.p.rv.xlen, reset=self.p.reset_vector)
        #fetch_addr_v = Signal(reset=True)
        #m.d.sync += addr.eq(addr + 0x20)
        #m.d.comb += [
        #    l1i.fetch_req.valid.eq(1),
        #    l1i.fetch_req.bits.eq(fetch_addr),
        #]
        #m.d.comb += self.bif.addr.eq(addr)

        return m   



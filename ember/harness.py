
from amaranth import *
from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Arbiter as WishboneArbiter
from amaranth_soc.wishbone import Decoder as WishboneDecoder

from .param import *

class EmberCoreHarness(Component):
    def __init__(self):
        signature = Signature({
            "bif": Out(BusInterface()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        core = m.submodules.core = EmberCore(EmberParams)
        connect(m, self.bif, flipped(core.bif))

        decoder = m.submodules.decoder = WishboneDecoder(
            addr_width=34, data_width=32, granularity=8,
            features=["err"],
        )
        #decoder.add(

        arbiter = m.submodules.arbiter = WishboneArbiter(
            addr_width=34, data_width=32, granularity=8
            features=["err"],
        )

        return m


def build_core_harness():
    from amaranth.back import verilog
    x = EmberCoreHarness()
    v = verilog.convert(x)
    print(v)


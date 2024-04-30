
from amaranth import *
from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Arbiter as WishboneArbiter
from amaranth_soc.wishbone import Decoder as WishboneDecoder

from .param import *

#class EmberCoreHarness(Component):
#    rom_bus: WishboneInterface(
#        addr_width=30, data_width=32, granularity=8,
#        features=["err"]
#    )
#
#    def __init__(self):
#        super().__init__()
#
#    def elaborate(self, platform):
#        m = Module()
#
#        core = m.submodules.core = EmberCore(EmberParams)
#
#        decoder = m.submodules.decoder = WishboneDecoder(
#            addr_width=30, data_width=32, granularity=8,
#            features=["err"],
#        )
#        decoder.add(self.rom_bus, addr=0xffff_0000)
#
#        arbiter = m.submodules.arbiter = WishboneArbiter(
#            addr_width=34, data_width=32, granularity=8,
#            features=["err"],
#        )
#        arbiter.add(core.l1i.bus)
#
#        return m



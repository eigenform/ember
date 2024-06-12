
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.param import *
from ember.sim.fakeram import *

class EmberCoreHarness(Component):
    def __init__(self):
        signature = Signature({
            "fakeram": Out(FakeRamInterface(width_words=8)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        core = m.submodules.core = EmberCore(EmberParams)

        return m


def build_core_harness():
    from amaranth.back import verilog
    x = EmberCoreHarness()
    #v = verilog.convert(x)
    #print(v)


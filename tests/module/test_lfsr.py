import unittest
from ember.common.lfsr import LFSR
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

class LFSRModule(Elaboratable):
    def __init__(self):
        self.lfsr = LFSR(degree=6)
        self.en = Signal()
        self.out = Signal(6)
    def elaborate(self, platform):
        m = Module()
        m.submodules.lfsr = lfsr = EnableInserter(self.en)(self.lfsr)
        m.d.comb += [ 
            self.out.eq(self.lfsr.value), 
        ]
        return m

def lfsr_enable_proc(dut: LFSRModule):
    for i in range(32):
        output = yield dut.out
        #print(f"{output:06b}")
        if i % 4 == 0:
            yield dut.en.eq(1)
        else:
            yield dut.en.eq(0)
        yield Tick()

class LFSRTests(unittest.TestCase):

    #def test_lfsr_values(self):
    #    dut = LFSR(degree=6)
    #    values = dut.generate()
    #    for value in values: print(value)

    def test_lfsr_enable(self):
        tb = Testbench(
            LFSRModule(),
            lfsr_enable_proc,
            "lfsr_enable"
        )
        tb.run()



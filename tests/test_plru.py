import unittest
from ember.common.replacement import TreePLRU
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def plru_test_proc(dut: TreePLRU):
    for i in range(8):
        output = yield dut.lru
        #if i % 4 == 0:
        #    yield dut.en.eq(1)
        #else:
        #    yield dut.en.eq(0)
        yield Tick()

#class TreePLRUTests(unittest.TestCase):

    #def test_lfsr_values(self):
    #    dut = LFSR(degree=6)
    #    values = dut.generate()
    #    for value in values: print(value)

    #def test_plru(self):
    #    print()
    #    tb = Testbench(
    #        TreePLRU(8),
    #        plru_test_proc,
    #        "test_plru"
    #    )
    #    tb.run()



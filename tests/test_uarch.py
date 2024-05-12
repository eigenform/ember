import unittest
from ember.param import *
from ember.riscv.encoding import *
from ember.riscv.inst import *
from ember.uarch.mop import *
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.lib.enum import *
from amaranth.back import verilog, rtlil

class RvEncodingUnitTests(unittest.TestCase):
    def test_mop_const(self):
        for name, mop in EmberParams().mops.items():
            c = mop.as_const()

    #def test_vaddr_layout(self):
    #    vaddr = Signal(EmberParams().vaddr)
    #    print(vaddr.sv32)


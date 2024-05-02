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
    def test_uop_const(self):
        print(EmberMop.layout.as_shape())

        for name, uop in EmberParams().decode.mop_group.members.items():
            c = uop.as_const()


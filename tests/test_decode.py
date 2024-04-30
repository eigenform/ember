import unittest
from ember.param import *
from ember.decode import *

from ember.riscv import *
from ember.riscv.encoding import *
from ember.sim.common import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def tb_decode_simple(dut: Rv32Decoder):
    return

class DecodeUnitTests(unittest.TestCase):
    def test_decode(self):
        tb = Testbench(
            Rv32Decoder(),
            tb_decode_simple,
            "tb_decode_simple"
        )
        tb.run()

        return

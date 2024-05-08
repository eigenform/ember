
import unittest
import functools
import operator

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.hdl._ir import PortDirection
from amaranth.utils import ceil_log2, exact_log2, bits_for
from amaranth.sim import *
from amaranth.back import verilog

from ember.sim.common import *
from ember.common import *

class CommonUnitTests(unittest.TestCase):
    @staticmethod
    def simulate(m):
        def wrapper(fn):
            sim = Simulator(m)
            sim.add_testbench(fn)
            sim.run()
        return wrapper

    def test_popcount(self):
        m = Module()
        i_val = Signal(5)
        o_val = Signal(ceil_log2(5))
        m.d.comb += o_val.eq(popcount(i_val))
        m1 = PopCount(5)
        #print(verilog.convert(m1, ports={
        #    "i": (m1.i, PortDirection.Input),
        #    "o": (m1.o, PortDirection.Output),
        #}))

        @self.simulate(m)
        def check_func():
            for x in range(32):
                yield i_val.eq(x)
                self.assertEqual((yield o_val), x.bit_count())


        @self.simulate(m1)
        def check_foo():
            for x in range(32):
                yield m1.i.eq(x)
                self.assertEqual((yield m1.o), x.bit_count())





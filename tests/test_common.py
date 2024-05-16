
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
from ember.common.coding import *

class CommonUnitTests(unittest.TestCase):
    @staticmethod
    def simulate(m):
        def wrapper(fn):
            sim = Simulator(m)
            sim.add_testbench(fn)
            sim.run()
        return wrapper

    def test_priority_mux(self):
        m = PriorityMux(unsigned(4), 4)
        #v = verilog.convert(m, emit_src=True, strip_internal_attrs=True)
        #print(v)

        @self.simulate(m)
        def wow():
            # Works? 
            yield m.val[0].eq(0b0001)
            yield m.val[1].eq(0b0010)
            yield m.val[2].eq(0b0100)
            yield m.val[3].eq(0b1000)
            for i in range(4):
                yield m.sel[0].eq(0)
                yield m.sel[1].eq(0)
                yield m.sel[2].eq(0)
                yield m.sel[3].eq(0)
                yield m.sel[i].eq(1)
                res = yield m.output
                #print("sel_{} => {:04b}".format(i, res))
                assert res == (1 << i)

            # Implicit default zero case
            yield m.sel[0].eq(0)
            yield m.sel[1].eq(0)
            yield m.sel[2].eq(0)
            yield m.sel[3].eq(0)
            res = yield m.output
            assert res == 0

            yield m.sel[0].eq(1)
            yield m.sel[1].eq(0)
            yield m.sel[2].eq(0)
            yield m.sel[3].eq(1)
            res = yield m.output
            assert res == (1 << 0)



    def test_chained_priority_encoder(self):
        dut = ChainedPriorityEncoder(8, 1)

        @self.simulate(dut)
        def it_works():
            yield dut.i.eq(0b1000_0000)
            o = yield dut.o[0]
            n = yield dut.n[0]
            assert o == 7
            assert n == 0


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





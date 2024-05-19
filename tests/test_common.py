
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
from ember.common.mem import *
from ember.common.coding import *

class CommonUnitTests(unittest.TestCase):
    @staticmethod
    def simulate_comb(m):
        def wrapper(fn):
            sim = Simulator(m)
            sim.add_testbench(fn)
            sim.run()
        return wrapper

    @staticmethod
    def simulate_sync(m):
        def wrapper(fn):
            sim = Simulator(m)
            sim.add_testbench(fn)
            sim.add_clock(1e-6)
            sim.run()
        return wrapper


    def test_banked_mem(self):
        dut = BankedMemory(4, 16, ArrayLayout(32, 4))
        #print(verilog.convert(dut))

        @self.simulate_sync(dut)
        def bypass_rw():
            yield dut.bank[0].wp.req.valid.eq(1)
            yield dut.bank[0].wp.req.addr.eq(0)
            for i in range(4):
                yield dut.bank[0].wp.req.data[i].eq(i)
            yield dut.bank[0].rp.req.valid.eq(1)
            yield dut.bank[0].rp.req.addr.eq(0)

            yield Tick()
            for i in range(4):
                v = yield dut.bank[0].rp.resp.data[i]
                assert v == i
            valid = yield dut.bank[0].rp.resp.valid
            assert valid



    def test_priority_mux(self):
        m = PriorityMux(unsigned(4), 4)
        #v = verilog.convert(m, emit_src=True, strip_internal_attrs=True)
        #print(v)

        @self.simulate_comb(m)
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



    def test_ember_priority_encoder(self):
        dut = EmberPriorityEncoder(8)
        #v = verilog.convert(dut, emit_src=False, strip_internal_attrs=True)
        #print(v)

        @self.simulate_comb(dut)
        def it_works():
            yield dut.i.eq(0b1000_0000)
            o = yield dut.o
            m = yield dut.mask
            n = yield dut.valid
            assert o == 7
            assert n == 1
            assert m == 0b1000_0000

            yield dut.i.eq(0b1000_0001)
            o = yield dut.o
            m = yield dut.mask
            n = yield dut.valid
            assert m == 0b0000_0001
            assert o == 0
            assert n == 1

            yield dut.i.eq(0b0000_0000)
            o = yield dut.o
            m = yield dut.mask
            n = yield dut.valid
            assert m == 0b0000_0000
            assert o == 0
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

        @self.simulate_comb(m)
        def check_func():
            for x in range(32):
                yield i_val.eq(x)
                self.assertEqual((yield o_val), x.bit_count())

        @self.simulate_comb(m1)
        def check_foo():
            for x in range(32):
                yield m1.i.eq(x)
                self.assertEqual((yield m1.o), x.bit_count())





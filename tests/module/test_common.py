
import unittest
import functools
import operator
import random

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
from ember.common.xbar import *

class Offset2BitmaskHarness(Component):
    def __init__(self, off_width: int, mask_width: int):
        self.off_width = off_width
        self.mask_width = mask_width
        super().__init__({
            "idx": In(off_width),
            "mask_off": Out(mask_width),
            "mask_lim": Out(mask_width),
        })
    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.mask_off.eq(offset2masklut(8, self.idx))
        m.d.comb += self.mask_lim.eq(limit2masklut(8, self.idx))
        return m

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
        def _1():
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
        def _1():
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

    def test_chained_priority_encoder(self):
        dut = ChainedPriorityEncoder(8, depth=3)

        @self.simulate_comb(dut)
        def _1():
            yield dut.i.eq(0b1000_1001)
            results = []
            for idx in range(3):
                o = yield dut.o[idx]
                valid = yield dut.valid[idx]
                mask = yield dut.mask[idx]
                results.append((o, valid, mask))
            assert results == [
                (0, 1, 0b0000_0001),
                (3, 1, 0b0000_1000),
                (7, 1, 0b1000_0000),
            ]


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
        def _1():
            for x in range(32):
                yield i_val.eq(x)
                self.assertEqual((yield o_val), x.bit_count())

        @self.simulate_comb(m1)
        def _2():
            for x in range(32):
                yield m1.i.eq(x)
                self.assertEqual((yield m1.o), x.bit_count())


    def test_simple_xbar(self):
        dut = SimpleCrossbar(2, 2)

        @self.simulate_comb(dut)
        def _1():

            yield dut.upstream_grant[0].eq(1)
            yield dut.upstream_grant[1].eq(1)
            yield dut.downstream_grant[0].eq(0)
            yield dut.downstream_grant[1].eq(1)
            s = yield dut.dst_idx[0]
            v = yield dut.grant[0]
            assert s == 1
            assert v == 1
            s = yield dut.dst_idx[1]
            v = yield dut.grant[1]
            assert s == 0
            assert v == 0

            yield dut.upstream_grant[0].eq(1)
            yield dut.upstream_grant[1].eq(1)
            yield dut.downstream_grant[0].eq(1)
            yield dut.downstream_grant[1].eq(1)
            s = yield dut.dst_idx[0]
            v = yield dut.grant[0]
            assert s == 0
            assert v == 1
            s = yield dut.dst_idx[1]
            v = yield dut.grant[1]
            assert s == 1
            assert v == 1


            yield dut.upstream_grant[0].eq(0)
            yield dut.upstream_grant[1].eq(1)
            yield dut.downstream_grant[0].eq(0)
            yield dut.downstream_grant[1].eq(1)
            s = yield dut.dst_idx[0]
            v = yield dut.grant[0]
            assert s == 0
            assert v == 0
            s = yield dut.dst_idx[1]
            v = yield dut.grant[1]
            assert s == 1
            assert v == 1

    def test_offset2bitmask(self):
        dut = Offset2BitmaskHarness(off_width=5, mask_width=8)

        @self.simulate_comb(dut)
        def _1():

            off_results = []
            lim_results = []
            for off in range(0, 0x20, 4):
                yield dut.idx.eq(off >> 2)
                mask_off = yield dut.mask_off
                mask_lim = yield dut.mask_lim
                off_results.append((off, mask_off))
                lim_results.append((off, mask_lim))
                print("{:02x} {:08b}".format(off, mask_lim))

            assert off_results == [
                (0x00, 0b1111_1111),
                (0x04, 0b1111_1110),
                (0x08, 0b1111_1100),
                (0x0c, 0b1111_1000),
                (0x10, 0b1111_0000),
                (0x14, 0b1110_0000),
                (0x18, 0b1100_0000),
                (0x1c, 0b1000_0000),
            ]
            assert lim_results == [
                (0x00, 0b0000_0001),
                (0x04, 0b0000_0011),
                (0x08, 0b0000_0111),
                (0x0c, 0b0000_1111),
                (0x10, 0b0001_1111),
                (0x14, 0b0011_1111),
                (0x18, 0b0111_1111),
                (0x1c, 0b1111_1111),
            ]








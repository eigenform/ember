
import inspect
import unittest
from ember.param import *
from ember.cache.l1i import *
from ember.cache.itlb import *
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

from struct import pack, unpack

def tb_data_array_rw(dut: L1ICacheDataArray):
    yield dut.wp_en.eq(1)
    yield dut.wp_data[0].eq(0xdeadc0de)

    yield Tick()
    yield dut.wp_en.eq(0)
    yield dut.wp_data[0].eq(0)
    yield dut.rp_en.eq(1)
    yield dut.rp_idx.eq(0)

    data = yield dut.rp_data[0][0]
    assert data == 0x00000000

    yield Tick()
    yield dut.rp_en.eq(0)
    yield dut.rp_idx.eq(0)
    data = yield dut.rp_data[0][0]
    assert data == 0xdeadc0de


def tb_l1itlb(dut: L1ICacheTLB):
    yield dut.fill_req.valid.eq(1)
    yield dut.fill_req.ppn.eq(0x1111)
    yield dut.fill_req.vpn.eq(0x1001)

    yield Tick()
    yield dut.fill_req.valid.eq(1)
    yield dut.fill_req.ppn.eq(0x2222)
    yield dut.fill_req.vpn.eq(0x2002)
    yield dut.req.valid.eq(1)
    yield dut.req.vpn.eq(0x1001)

    yield Tick()
    yield dut.fill_req.valid.eq(0)
    yield dut.fill_req.ppn.eq(0)
    yield dut.fill_req.vpn.eq(0)
    yield dut.req.valid.eq(1)
    yield dut.req.vpn.eq(0x2002)
    valid = yield dut.resp.valid
    ppn   = yield dut.resp.ppn
    assert valid == 1
    assert ppn == 0x1111

    yield Tick()
    yield dut.req.valid.eq(0)
    yield dut.req.vpn.eq(0)
    valid = yield dut.resp.valid
    ppn   = yield dut.resp.ppn
    assert valid == 1
    assert ppn == 0x2222

class L1ICacheHarness(object):
    def __init__(self, dut: L1ICache):
        self.dut = dut

    def drive_write_port(self, set_idx, way_idx, tag, line):
        assert len(line) == 4
        yield self.dut.wp.req.valid.eq(1)
        yield self.dut.wp.req.set.eq(set_idx)
        yield self.dut.wp.req.way.eq(way_idx)
        yield self.dut.wp.req.tag_data.valid.eq(1)
        yield self.dut.wp.req.tag_data.tag.eq(tag)
        yield self.dut.wp.req.line_data[0].eq(line[0])
        yield self.dut.wp.req.line_data[1].eq(line[1])
        yield self.dut.wp.req.line_data[2].eq(line[2])
        yield self.dut.wp.req.line_data[3].eq(line[3])

    def clear_write_port(self):
        yield self.dut.wp.req.valid.eq(0)
        yield self.dut.wp.req.set.eq(0)
        yield self.dut.wp.req.way.eq(0)
        yield self.dut.wp.req.tag_data.valid.eq(0)
        yield self.dut.wp.req.tag_data.tag.eq(0)
        yield self.dut.wp.req.line_data.eq(0)

    def clear_read_port(self):
        yield self.dut.rp.req.set.eq(0)
        yield self.dut.rp.req.valid.eq(0)

    def drive_read_port(self, set_idx):
        yield self.dut.rp.req.set.eq(set_idx)
        yield self.dut.rp.req.valid.eq(1)

    def sample_read_port(self):
        valid = yield self.dut.rp.resp.valid
        tag_data = []
        tag_valid = []
        line_data = []
        for way in range(EmberParams.l1i.num_ways):
            v = yield self.dut.rp.resp.tag_data[way].valid
            tag = yield self.dut.rp.resp.tag_data[way].tag
            line = []
            for i in range(EmberParams.l1i.line_depth):
                j = yield self.dut.rp.resp.line_data[way][i]
                line.append(j)
            tag_data.append(tag)
            tag_valid.append(v)
            line_data.append(line)
        return (valid, tag_data, tag_valid, line_data)

def tb_l1icache_rw(dut: L1ICache):
    cache = L1ICacheHarness(dut)
    yield from cache.drive_write_port(1, 1, 0x4, [1,2,3,4])
    yield Tick()
    yield from cache.clear_write_port()
    yield from cache.drive_read_port(1)
    yield Tick()
    yield from cache.clear_read_port()
    valid, tag_data, tag_valid, line_data = yield from cache.sample_read_port()
    assert valid == 1
    assert tag_valid[1] == 1
    assert tag_data[1] == 0x4
    assert line_data[1] == [1,2,3,4]


class L1ICacheTests(unittest.TestCase):

    #def test_l1icache_elaborate(self):
    #    dut = L1ICache(EmberParams)
    #    with open("/tmp/L1ICache.v", "w") as f:
    #        f.write(verilog.convert(dut))

    def test_l1icache_data_array_rw(self):
        tb = Testbench(
            L1ICacheDataArray(EmberParams.l1i), 
            tb_data_array_rw,
            "tb_data_array_rw"
        )
        tb.run()

    def test_l1itlb(self):
        tb = Testbench(
            L1ICacheTLB(EmberParams.l1i), 
            tb_l1itlb,
            "tb_l1itlb"
        )
        tb.run()

    def test_l1icache_rw(self):
        tb = Testbench(
            L1ICache(EmberParams),
            tb_l1icache_rw,
            "tb_l1icache_rw"
        )
        tb.run()


    #def test_sim(self):
    #    dut = L1ICache(EmberParams)
    #    sets = EmberParams.l1i.num_sets 
    #    ways = EmberParams.l1i.num_ways
    #    print()

    #    #print(dut.__annotations__)
    #    def foo():
    #        for idx in range(16):
    #            yield dut.rp.set.eq(idx)
    #            yield dut.rp.en.eq(1)
    #            Tick()

    #            for way_idx in range(0, ways):
    #                valid     = yield dut.rp.valid
    #                line_data = yield dut.rp.line_data[way_idx]
    #                tag_data  = yield dut.rp.tag_data[way_idx]
    #                print(f"valid={valid}")
    #                if valid == 1:
    #                    print("valid set")
    #                    print(line_data)
    #                    print(tag_data)


    #    sim = Simulator(dut)
    #    sim.add_clock(1e-6)
    #    sim.add_process(foo)
    #    with open("/tmp/test_l1i.vcd", "w") as f:
    #        with sim.write_vcd(vcd_file=f):
    #            sim.run()



import inspect
import unittest
import logging
#logging.basicConfig(level=logging.DEBUG)

from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ifill import *
from ember.sim.common import Testbench
from ember.sim.fakeram import *

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
    yield dut.fill_req.pte.eq(0x1111_1111)
    yield dut.fill_req.vpn.eq(0x1001)

    yield Tick()
    yield dut.fill_req.valid.eq(1)
    yield dut.fill_req.pte.eq(0x2222_2222)
    yield dut.fill_req.vpn.eq(0x2002)
    yield dut.rp.req.valid.eq(1)
    yield dut.rp.req.vpn.eq(0x1001)

    yield Tick()
    yield dut.fill_req.valid.eq(0)
    yield dut.fill_req.pte.eq(0)
    yield dut.fill_req.vpn.eq(0)
    yield dut.rp.req.valid.eq(1)
    yield dut.rp.req.vpn.eq(0x2002)
    valid = yield dut.rp.resp.valid
    pte   = yield dut.rp.resp.pte
    assert valid == 1
    assert pte == 0x1111_1111

    yield Tick()
    yield dut.rp.req.valid.eq(0)
    yield dut.rp.req.vpn.eq(0)
    valid = yield dut.rp.resp.valid
    pte   = yield dut.rp.resp.pte
    assert valid == 1
    assert pte == 0x2222_2222

class L1ICacheHarness(object):
    def __init__(self, dut: L1ICache):
        self.dut = dut

    def drive_write_port(self, wp_idx, set_idx, way_idx, tag, line):
        assert len(line) == 4
        yield self.dut.wp[wp_idx].req.valid.eq(1)
        yield self.dut.wp[wp_idx].req.set.eq(set_idx)
        yield self.dut.wp[wp_idx].req.way.eq(way_idx)
        yield self.dut.wp[wp_idx].req.tag_data.valid.eq(1)
        yield self.dut.wp[wp_idx].req.tag_data.ppn.eq(tag)
        yield self.dut.wp[wp_idx].req.line_data[0].eq(line[0])
        yield self.dut.wp[wp_idx].req.line_data[1].eq(line[1])
        yield self.dut.wp[wp_idx].req.line_data[2].eq(line[2])
        yield self.dut.wp[wp_idx].req.line_data[3].eq(line[3])

    def clear_write_port(self, wp_idx):
        yield self.dut.wp[wp_idx].req.valid.eq(0)
        yield self.dut.wp[wp_idx].req.set.eq(0)
        yield self.dut.wp[wp_idx].req.way.eq(0)
        yield self.dut.wp[wp_idx].req.tag_data.valid.eq(0)
        yield self.dut.wp[wp_idx].req.tag_data.ppn.eq(0)
        yield self.dut.wp[wp_idx].req.line_data.eq(0)

    def clear_read_port(self, rp_idx):
        yield self.dut.rp[rp_idx].req.set.eq(0)
        yield self.dut.rp[rp_idx].req.valid.eq(0)

    def drive_read_port(self, rp_idx, set_idx):
        yield self.dut.rp[rp_idx].req.set.eq(set_idx)
        yield self.dut.rp[rp_idx].req.valid.eq(1)

    def sample_read_port(self, rp_idx):
        valid = yield self.dut.rp[rp_idx].resp.valid
        tag_data = []
        tag_valid = []
        line_data = []
        for way in range(EmberParams.l1i.num_ways):
            v = yield self.dut.rp[rp_idx].resp.tag_data[way].valid
            tag = yield self.dut.rp[rp_idx].resp.tag_data[way].ppn
            line = []
            for i in range(EmberParams.l1i.line_depth):
                j = yield self.dut.rp[rp_idx].resp.line_data[way][i]
                line.append(j)
            tag_data.append(tag)
            tag_valid.append(v)
            line_data.append(line)
        return (valid, tag_data, tag_valid, line_data)

def tb_l1icache_rw(dut: L1ICache):
    cache = L1ICacheHarness(dut)
    yield from cache.drive_write_port(0, 1, 1, 0x4, [1,2,3,4])
    yield Tick()
    yield from cache.clear_write_port(0)
    yield from cache.drive_read_port(0, 1)
    yield Tick()
    yield from cache.clear_read_port(0)
    valid, tag_data, tag_valid, line_data = yield from cache.sample_read_port(0)
    assert valid == 1
    assert tag_valid[1] == 1
    assert tag_data[1] == 0x4
    assert line_data[1] == [1,2,3,4]

def tb_l1ifill(dut: L1IFillUnit):
    #log = logging.getLogger("tb_l1ifill")
    ram = FakeRam(0x0000_1000)
    ram.write_bytes(0, bytearray([i for i in range(1, 256)]))

    yield dut.l1i_wp[0].resp.valid.eq(1)

    ready = yield dut.sts.ready
    assert ready == 1
    
    yield dut.req.addr.eq(0x0000_0000)
    yield dut.req.way.eq(1)
    yield dut.req.valid.eq(1)

    ready = 0
    cyc = 0
    while ready == 0:
        if cyc >= 16:
            assert 1==0, f"timeout after {cyc} cycles"
        yield Tick()
        yield dut.req.addr.eq(0x0000_0000)
        yield dut.req.way.eq(0)
        yield dut.req.valid.eq(0)
        yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
        ready = yield dut.sts.ready
        cyc += 1
    #log.debug(f"Fill completed in {cyc} cycles")

    ready = yield dut.sts.ready
    assert ready == 1, f"{ready}"


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

    def test_l1ifill(self):
        tb = Testbench(
            L1IFillUnit(EmberParams),
            tb_l1ifill,
            "tb_l1ifill"
        )
        tb.run()


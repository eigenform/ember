import inspect
import unittest
import logging

from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ifill import *
from ember.sim.common import Testbench, ClkMgr
from ember.sim.fakeram import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

from struct import pack, unpack

class L1IFillHarness(Component):
    def __init__(self, p: EmberParams):
        self.p = p
        super().__init__(Signature({
            "fakeram": Out(FakeRamInterface(p.l1i.line_depth).flip()).array(2),
            "port": In(L1IFillPort(p).flip()),
            "l1i_rp": In(L1ICacheReadPort(p).flip()),
        }))

    def elaborate(self, platform):
        m = Module()
        m.submodules.l1i = l1i = L1ICache(self.p)
        m.submodules.ifill = ifill = NewL1IFillUnit(self.p)

        connect(m, self.port, ifill.port[0])
        connect(m, self.fakeram[0], ifill.fakeram[0])
        connect(m, self.fakeram[1], ifill.fakeram[1])
        connect(m, ifill.l1i_wp[0], l1i.wp[0])
        connect(m, ifill.l1i_wp[1], l1i.wp[1])
        connect(m, self.l1i_rp, l1i.rp[0])

        return m

def tb_l1ifill_2(dut: L1IFillHarness):
    print()
    clk = ClkMgr()
    ram = FakeRam(0x0000_2000)
    ram.write_bytes(0x1000, bytearray([i for i in range(1, 256)]))

    yield dut.port.req.addr.eq(0x0000_1000)
    yield dut.port.req.way.eq(1)
    yield dut.port.req.valid.eq(1)
    yield dut.port.req.blocks.eq(4)
    yield from clk.step()

    yield dut.port.req.addr.eq(0)
    yield dut.port.req.way.eq(0)
    yield dut.port.req.valid.eq(0)
    yield dut.port.req.blocks.eq(0)
    cyc = 1

    resp_valid = 0
    while resp_valid == 0:
        if cyc >= 16: 
            raise Exception("timed out waiting for ifill response")
        yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
        resp_valid = yield dut.port.resp.valid
        yield from clk.step()
        cyc += 1
    print(f"transaction complete in {cyc} cycles")

    for set_idx in range(0, 4):
        yield dut.l1i_rp.req.valid.eq(1)
        yield dut.l1i_rp.req.set.eq(set_idx)
        yield from clk.step()
        for way_idx in range(dut.p.l1i.num_ways):
            v = yield dut.l1i_rp.resp.tag_data[way_idx].valid
            ppn = yield dut.l1i_rp.resp.tag_data[way_idx].ppn
            line = []
            for i in range(dut.p.l1i.line_depth):
                j = yield dut.l1i_rp.resp.line_data[way_idx][i]
                line.append(unpack("<L", pack("<L", j))[0])
            if v == 1:
                print(f"way {way_idx}: ", [ "{:08x}".format(x) for x in line ])



def tb_l1ifill(dut: NewL1IFillUnit):
    print()
    clk = ClkMgr()
    ram = FakeRam(0x0000_2000)
    ram.write_bytes(0x1000, bytearray([i for i in range(1, 256)]))

    #yield dut.l1i_wp[0].resp.valid.eq(1)

    #ready = yield dut.sts.ready
    #assert ready == 1
    
    yield dut.port[0].req.addr.eq(0x0000_1000)
    yield dut.port[0].req.way.eq(1)
    yield dut.port[0].req.valid.eq(1)
    yield dut.port[0].req.blocks.eq(4)

    #clk.start("l1i_fill_4blk_latency", limit=16)

    resp_valid = 0
    cyc = 0
    while resp_valid == 0:
        if cyc >= 16: 
            break
        yield from clk.step()
        yield dut.port[0].req.addr.eq(0x0000_0000)
        yield dut.port[0].req.way.eq(0)
        yield dut.port[0].req.valid.eq(0)
        yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
        resp_valid = yield dut.port[0].resp.valid
        cyc += 1

    #clk.stop("l1i_fill_4blk_latency")
    resp_valid = yield dut.port[0].resp.valid
    #assert resp_valid == 1, f"{resp_valid}"
    #clk.print_events()

    for _ in range(8):
        yield from clk.step()



class L1IFillUnitTests(unittest.TestCase):
    def test_l1ifill(self):
        tb = Testbench(
            NewL1IFillUnit(EmberParams()),
            tb_l1ifill,
            "tb_l1ifill"
        )
        tb.run()

    def test_l1ifill_2(self):
        tb = Testbench(
            L1IFillHarness(EmberParams()),
            tb_l1ifill_2,
            "tb_l1ifill_2"
        )
        tb.run()


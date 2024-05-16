
import unittest
from ember.param import *
from ember.front.l1i import L1ICache
from ember.front.itlb import L1ICacheTLB
from ember.front.fetch import FetchUnit
from ember.front.ftq import FetchTargetQueue, FTQAllocRequest
from ember.front.ifill import L1IFillUnit
from ember.sim.common import Testbench
from ember.uarch.fetch import *
from ember.sim.fakeram import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

class FetchUnitHarness(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "fetch_req": In(FetchRequest(param)),
            "fetch_resp": Out(FetchResponse(param)),
            "alloc_req": In(FTQAllocRequest(param)),

            "fakeram": Out(FakeRamInterface()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        ftq   = m.submodules.ftq   = FetchTargetQueue(self.p)
        ifu   = m.submodules.ifu   = FetchUnit(self.p)
        l1i   = m.submodules.l1i   = L1ICache(self.p)
        itlb  = m.submodules.itlb  = L1ICacheTLB(self.p.l1i)
        ifill = m.submodules.ifill = L1IFillUnit(self.p)

        connect(m, ifu.l1i_rp, l1i.rp)
        connect(m, ifu.tlb_rp, itlb.rp)
        #connect(m, ifu.req, flipped(self.fetch_req))
        #connect(m, ifu.resp, flipped(self.fetch_resp))
        connect(m, ftq.fetch_req, ifu.req)
        connect(m, ftq.fetch_resp, ifu.resp)
        connect(m, ftq.ifill_resp, ifill.resp)
        connect(m, ftq.alloc_req, flipped(self.alloc_req))

        connect(m, ifu.ifill_req, ifill.req)
        connect(m, ifu.ifill_sts, ifill.sts)
        connect(m, ifill.l1i_wp, l1i.wp)
        connect(m, ifill.fakeram, flipped(self.fakeram))
        return m


def tb_fetch_simple(dut: FetchUnitHarness):
    print()
    ram = FakeRam(0x0000_1000)
    ram.write_bytes(0, bytearray([i for i in range(1, 256)]))

    yield dut.alloc_req.valid.eq(1)
    yield dut.alloc_req.passthru.eq(1)
    yield dut.alloc_req.vaddr.eq(0x0000_0000)

    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)
    yield dut.alloc_req.vaddr.eq(0x0000_0020)

    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)
    yield dut.alloc_req.vaddr.eq(0x0000_0040)

    yield dut.alloc_req.valid.eq(0)
    yield dut.alloc_req.passthru.eq(0)
    yield dut.alloc_req.vaddr.eq(0x0000_0000)


    for _ in range(32):
        yield Tick()
        yield from ram.run(dut.fakeram.req, dut.fakeram.resp)


class FetchUnitTests(unittest.TestCase):
    def test_fetch_elab(self):
        #m = FetchUnit(EmberParams)
        m = FetchUnitHarness(EmberParams)
        with open("/tmp/FetchUnitHarness.v", "w") as f:
            f.write(verilog.convert(m))

    def test_fetch_simple(self):
        tb = Testbench(
            FetchUnitHarness(EmberParams), 
            tb_fetch_simple,
            "tb_fetch_simple"
        )
        tb.run()



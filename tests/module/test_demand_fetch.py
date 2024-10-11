import unittest
from ember.param import *
from ember.sim.common import Testbench
from ember.sim.fakeram import *
from ember.front.demand_fetch import *
from ember.front.demand_fetch import DemandFetchRequest
from ember.uarch.front import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil
from amaranth.lib.enum import Enum

class DemandFetchUnitHarness(Component):
    def __init__(self, param: EmberParams): 
        self.p = param
        signature = Signature({
            "req": In(DemandFetchRequest(param)),
            "fakeram": Out(FakeRamInterface(param.l1i.line_depth)).array(2),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        m.submodules.dfu  = dfu  = DemandFetchUnit(self.p)
        m.submodules.l1i  = l1i  = L1ICache(self.p)
        m.submodules.itlb = itlb = L1ICacheTLB(self.p)
        m.submodules.ifill = ifill = NewL1IFillUnit(self.p)
        #m.submodules.pdu = pdu = PredecodeUnit(self.p)

        connect(m, flipped(self.req), dfu.req)
        connect(m, dfu.l1i_rp, l1i.rp[0])
        connect(m, dfu.tlb_rp, itlb.rp)
        #connect(m, dfu.pd_req, pdu.req)

        connect(m, dfu.ifill, ifill.port[0])
        #connect(m, dfu.ifill_req, ifill.port[0].req)

        connect(m, dfu.ifill_sts, ifill.sts)
        connect(m, ifill.fakeram[0], flipped(self.fakeram[0]))
        connect(m, ifill.fakeram[1], flipped(self.fakeram[1]))
        connect(m, ifill.l1i_wp[0], l1i.wp[0])
        connect(m, ifill.l1i_wp[1], l1i.wp[1])

        return m

def tb_demand_fetch(dut: DemandFetchUnit):
    ram = FakeRam(0x0001_0000)
    for addr in range(0x1000, 0x2000, 4):
        ram.write_word(addr, addr)

    # Dummy [padding] cycle
    yield Tick()

    # Drive a demand request
    yield dut.req.valid.eq(1)
    yield dut.req.vaddr.eq(0x0000_1008)
    yield dut.req.passthru.eq(1)
    yield dut.req.lines.eq(1)
    yield Tick()
    yield dut.req.valid.eq(0)
    yield dut.req.vaddr.eq(0x0000_0000)
    yield dut.req.passthru.eq(0)
    yield dut.req.lines.eq(0)

    # Run the pipeline for a few cycles
    for i in range(24):
        yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
        yield from ram.run(dut.fakeram[1].req, dut.fakeram[1].resp, pipe=1)
        yield Tick()


class DemandFetchTests(unittest.TestCase):
    def test_demand(self):
        tb = Testbench(
            DemandFetchUnitHarness(EmberParams()),
            tb_demand_fetch,
            "tb_demand_fetch"
        )
        tb.run()



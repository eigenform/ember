import unittest
from ember.param import *
from ember.sim.common import Testbench
from ember.sim.fakeram import *
from ember.front.demand_fetch import *
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
            "fakeram": Out(FakeRamInterface(param.l1i.line_depth)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        m.submodules.dfu  = dfu  = DemandFetchUnit(self.p)
        m.submodules.l1i  = l1i  = L1ICache(self.p)
        m.submodules.itlb = itlb = L1ICacheTLB(self.p)

        connect(m, flipped(self.req), dfu.req)
        connect(m, dfu.l1i_rp, l1i.rp[0])
        connect(m, dfu.tlb_rp, itlb.rp)

        return m

def tb_demand_fetch(dut: DemandFetchUnit):
    ram = FakeRam(0x0000_1000)
    for i in range(10):
        yield dut.req.valid.eq(1)
        yield dut.req.vaddr.eq(0x0000_1000)
        yield dut.req.passthru.eq(1)
        yield dut.req.blocks.eq(4)
        yield Tick()
        yield from ram.run(dut.fakeram.req, dut.fakeram.resp)


    #yield dut.alloc_req.valid.eq(0)
    #yield dut.alloc_req.passthru.eq(0)
    #yield dut.alloc_req.vaddr.eq(0)

    #yield Tick()

class DemandFetchTests(unittest.TestCase):
    def test_demand(self):
        tb = Testbench(
            DemandFetchUnitHarness(EmberParams()),
            tb_demand_fetch,
            "tb_demand_fetch"
        )
        tb.run()



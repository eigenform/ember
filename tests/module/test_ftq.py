import unittest
from ember.param import *
from ember.sim.common import Testbench
from ember.sim.fakeram import *
from ember.front.ftq import *
from ember.uarch.front import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil
from amaranth.lib.enum import Enum

def tb_ftq_simple(dut: FetchTargetQueue):
    for i in range(10):
        yield dut.alloc_req.valid.eq(1)
        yield dut.alloc_req.passthru.eq(1)
        yield dut.alloc_req.vaddr.eq(0x0000_1000 | (i * 0x20))
        yield Tick()
    yield dut.alloc_req.valid.eq(0)
    yield dut.alloc_req.passthru.eq(0)
    yield dut.alloc_req.vaddr.eq(0)

    yield Tick()

class FTQTests(unittest.TestCase):
    def test_ftq_elaborate(self):
        dut = FetchTargetQueue(EmberParams())
        with open("/tmp/FetchTargetQueue.v", "w") as f:
            f.write(verilog.convert(dut, 
                emit_src=False, 
                strip_internal_attrs=True, 
                name="FetchTargetQueue"
            ))


    def test_ftq_simple(self):
        tb = Testbench(
            FetchTargetQueue(EmberParams()),
            tb_ftq_simple,
            "tb_ftq_simple"
        )
        tb.run()




import unittest
from ember.param import *
from ember.cache.l1i import *
from ember.cache.itlb import *
from ember.fetch import *
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def tb_fetch_simple(dut: FetchUnit):
    yield dut.req.valid.eq(1)
    yield dut.req.vaddr.eq(0x00010000)
    yield Tick()
    yield Tick()
    yield Tick()
    yield Tick()
    yield Tick()
    yield Tick()
    yield Tick()
    yield Tick()
    yield Tick()

class FetchUnitTests(unittest.TestCase):
    #def test_fetch_elab(self):
    #    m = FetchUnit(EmberParams)
    #    with open("/tmp/FetchUnit.v", "w") as f:
    #        f.write(verilog.convert(m))

    def test_fetch_simple(self):
        tb = Testbench(
            FetchUnit(EmberParams), 
            tb_fetch_simple,
            "tb_fetch_simple"
        )
        tb.run()



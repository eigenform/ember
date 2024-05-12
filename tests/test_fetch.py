
import unittest
from ember.param import *
from ember.cache.l1i import *
from ember.cache.itlb import *
from ember.fetch import *
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil


def tb_fetch_simple(dut: FetchUnitHarness):
    ram = FakeRam(0x0000_1000)
    ram.write_bytes(0, bytearray([i for i in range(1, 256)]))

    print()
    yield dut.fetch_req.valid.eq(1)
    yield dut.fetch_req.vaddr.eq(0x0000_0000)
    yield dut.fetch_req.passthru.eq(1)
    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)
    yield dut.fetch_req.vaddr.eq(0x0000_0020)

    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)
    yield dut.fetch_req.vaddr.eq(0x0000_0040)

    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)
    yield dut.fetch_req.vaddr.eq(0x0000_0060)

    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)
    yield dut.fetch_req.vaddr.eq(0x0000_0080)

    yield Tick()
    yield from ram.run(dut.fakeram.req, dut.fakeram.resp)

class FetchUnitTests(unittest.TestCase):
    #def test_fetch_elab(self):
    #    m = FetchUnit(EmberParams)
    #    with open("/tmp/FetchUnit.v", "w") as f:
    #        f.write(verilog.convert(m))

    def test_fetch_simple(self):
        tb = Testbench(
            FetchUnitHarness(EmberParams), 
            tb_fetch_simple,
            "tb_fetch_simple"
        )
        tb.run()



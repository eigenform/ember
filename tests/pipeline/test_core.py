import unittest
from ember.param import *

from ember.sim.common import Testbench
from ember.uarch.front import *
from ember.sim.fakeram import *
from ember.core import EmberCore

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil


def tb_core_simple(dut: EmberCore):
    print()
    ram = FakeRam(0x0000_1000)
    with open("./rv32/branches.bin", "rb") as f:
        data = bytearray(f.read())
    #ram.write_bytes(0, bytearray([i for i in range(1, 256)]))
    ram.write_bytes(0, data)

    yield dut.dbg_cf_req.valid.eq(1)
    yield dut.dbg_cf_req.pc.eq(0x0000_0000)
    yield Tick()
    yield dut.dbg_cf_req.valid.eq(0)
    yield dut.dbg_cf_req.pc.eq(0x0000_0000)

    cyc = 0
    done = False
    while not done:
        if cyc >= 64:
            break
        yield Tick()
        yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
        yield from ram.run(dut.fakeram[1].req, dut.fakeram[1].resp, pipe=1)
        cyc += 1


class EmberCoreTests(unittest.TestCase):
    #def test_core_elab(self):
    #    m = EmberCore(EmberParams())
    #    with open("/tmp/EmberCore.v", "w") as f:
    #        f.write(verilog.convert(m, emit_src=False, name="EmberCore"))

    def test_core_simple(self):
        tb = Testbench(
            EmberCore(EmberParams()), 
            tb_core_simple,
            "tb_core_simple"
        )
        tb.run()



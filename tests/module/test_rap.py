import unittest
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.sim.common import Testbench
from ember.front.bp.rap import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def tb_rap_rw(dut: ReturnAddressPredictor):
    #yield dut.req.valid.eq(1)
    #yield dut.req.idx.eq(3)
    #yield dut.write_req.valid.eq(1)
    #yield dut.write_req.idx.eq(3)
    #yield dut.write_req.addr.eq(0xdeadc0de)
    #yield Tick()

    #addr = yield dut.resp.addr
    #valid = yield dut.resp.valid
    #assert addr == 0xdeadc0de
    #assert valid == 1
    #yield dut.req.valid.eq(0)
    #yield dut.req.idx.eq(0)
    #yield dut.write_req.valid.eq(0)
    #yield dut.write_req.idx.eq(0)
    #yield dut.write_req.addr.eq(0)
    #yield Tick()

    #yield dut.req.valid.eq(1)
    #yield dut.req.idx.eq(3)
    #yield Tick()
    #addr = yield dut.resp.addr
    #valid = yield dut.resp.valid
    #assert addr == 0xdeadc0de
    #assert valid == 1

    yield Tick()





class RAPUnitTests(unittest.TestCase):
    def test_rap_elaborate(self):
        dut = ReturnAddressPredictor(8)
        with open("/tmp/ReturnAddressPredictor.v", "w") as f:
            f.write(verilog.convert(dut))


    def test_rap_rw(self):
        tb = Testbench(
            ReturnAddressPredictor(8),
            tb_rap_rw,
            "tb_rap_rw"
        )
        tb.run()



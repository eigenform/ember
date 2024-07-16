
import unittest
from ember.param import *

from tests.common import *

from ember.sim.common import *
from ember.uarch.front import *
from ember.sim.fakeram import *
from ember.core import EmberFrontend

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def tb_fetch_miss2hit(dut: EmberFrontend):
    clk = ClkMgr()
    ram = FakeRam(0x0000_1000)
    with open("./rv32/branches.bin", "rb") as f:
        data = bytearray(f.read())
    #ram.write_bytes(0, bytearray([i for i in range(1, 256)]))
    ram.write_bytes(0, data)

    clk.start("cf_req_to_l1i_replay_hit", limit=16)
    yield dut.dbg_cf_req.valid.eq(1)
    yield dut.dbg_cf_req.pc.eq(0x0000_0000)

    yield from clk.step()
    yield dut.dbg_cf_req.valid.eq(0)
    yield dut.dbg_cf_req.pc.eq(0x0000_0000)

    done = False
    while not done:
        yield from clk.step()
        yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
        yield from ram.run(dut.fakeram[1].req, dut.fakeram[1].resp, pipe=1)
        valid = yield dut.dbg_fetch_resp.valid
        s = yield dut.dbg_fetch_resp.sts
        sts = FetchResponseStatus(s)
        done = (valid == 1) and (sts == FetchResponseStatus.L1_HIT)

    clk.stop("cf_req_to_l1i_replay_hit")
    data_miss2hit = []
    ftq_idx = yield dut.dq_up.data[0].ftq_idx
    for i in range(ram.width_words):
        d = yield dut.dq_up.data[0].data[i]
        data_miss2hit.append(d)

    #clk.start("cf_req_to_l1i_hit", limit=8)
    #yield dut.dbg_cf_req.valid.eq(1)
    #yield dut.dbg_cf_req.pc.eq(0x0000_0000)

    #yield from clk.step()
    #yield dut.dbg_cf_req.valid.eq(0)
    #yield dut.dbg_cf_req.pc.eq(0x0000_0000)

    #done = False
    #while not done:
    #    yield from clk.step()
    #    yield from ram.run(dut.fakeram[0].req, dut.fakeram[0].resp)
    #    yield from ram.run(dut.fakeram[1].req, dut.fakeram[1].resp, pipe=1)
    #    valid = yield dut.dbg_fetch_resp.valid
    #    s = yield dut.dbg_fetch_resp.sts
    #    sts = FetchResponseStatus(s)
    #    done = (valid == 1) and (sts == FetchResponseStatus.L1_HIT)

    #clk.stop("cf_req_to_l1i_hit")
    #data_hit = []
    #ftq_idx = yield dut.dq_up.data[0].ftq_idx
    #for i in range(ram.width_words):
    #    d = yield dut.dq_up.data[0].data[i]
    #    data_hit.append(d)
    #assert data_hit == data_miss2hit

    yield from clk.step()

    clk.print_events()


class FetchUnitTests(EmberTestCase):
    
    #def test_fetch_elab(self):
    #    m = EmberFrontend(EmberParams())
    #    with open("/tmp/EmberFrontend.v", "w") as f:
    #        f.write(verilog.convert(m, emit_src=False, name="EmberFrontend"))

    def test_fetch_miss2hit(self):
        tb = Testbench(
            EmberFrontend(EmberParams()), 
            tb_fetch_miss2hit,
            "tb_fetch_miss2hit"
        )
        tb.run()



import unittest
from ember.param import *
from ember.front.predecode import *

from ember.riscv.inst import *
from ember.riscv.encoding import *
from ember.uarch.mop import *
from ember.sim.common import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def tb_predecode_simple(dut: Rv32Predecoder):
    yield dut.inst_valid.eq(1)

    # Return (jalr x0, x1, 0)
    yield dut.inst.eq(0x00008067)
    yield Delay(1)
    cf_op = yield dut.info.cf_op
    rd  = yield dut.info.rd
    rs1 = yield dut.info.rs1
    assert rs1 == 1 or rs1 == 5
    assert ControlFlowOp(cf_op) == ControlFlowOp.RET

    # Direct call (jal x1, imm)
    yield dut.inst.eq(0x020000ef)
    yield Delay(1)
    cf_op = yield dut.info.cf_op
    rd = yield dut.info.rd
    assert rd == 1 or rd == 5
    assert ControlFlowOp(cf_op) == ControlFlowOp.CALL_DIR

    # Indirect call (jalr x1, x6, 0)
    yield dut.inst.eq(0x000300e7)
    yield Delay(1)
    cf_op = yield dut.info.cf_op
    rd = yield dut.info.rd
    assert rd == 1 or rd == 5
    assert ControlFlowOp(cf_op) == ControlFlowOp.CALL_IND

    # Indirect jump (jalr x0, x6, 0)
    yield dut.inst.eq(0x00030067)
    yield Delay(1)
    cf_op = yield dut.info.cf_op
    rd = yield dut.info.rd
    rs1 = yield dut.info.rs1
    assert rd == 0
    assert rs1 == 6
    assert ControlFlowOp(cf_op) == ControlFlowOp.JUMP_IND

    # Direct jump (jal x0, imm)
    yield dut.inst.eq(0x00c0006f)
    yield Delay(1)
    cf_op = yield dut.info.cf_op
    rd = yield dut.info.rd
    assert rd == 0
    assert ControlFlowOp(cf_op) == ControlFlowOp.JUMP_DIR

    # Indirect jump (jalr x1, x1, 0)
    yield dut.inst.eq(0x000080e7)
    yield Delay(1)
    cf_op = yield dut.info.cf_op
    rd = yield dut.info.rd
    assert rd == 1
    assert ControlFlowOp(cf_op) == ControlFlowOp.CALL_IND






class PredecodeUnitTests(unittest.TestCase):
    def test_predecode_simple(self):
        tb = TestbenchComb(
            Rv32Predecoder(EmberParams()),
            tb_predecode_simple,
            "tb_predecode_simple"
        )
        tb.run()
        return

    def test_pdu_elaborate(self):
        dut = PredecodeUnit(EmberParams())
        with open("/tmp/PredecodeUnit.v", "w") as f:
            f.write(verilog.convert(dut, name="PredecodeUnit"))
        with open("/tmp/PredecodeUnit.rtlil", "w") as f:
            f.write(rtlil.convert(dut, name="PredecodeUnit"))





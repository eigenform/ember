import unittest
from ember.param import *
from ember.decode import *

from ember.riscv.inst import *
from ember.riscv.encoding import *
from ember.uarch.mop import *
from ember.sim.common import *

from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

def tb_decode_simple(dut: Rv32GroupDecoder):
    RvInstId = dut.p.decode.inst_group.enum_type()

    yield dut.inst.eq(0xffff_f0b7)
    alu_op = yield dut.uop.alu_op
    print(AluOp(alu_op))
    yield Tick()
    mop = yield dut.mop
    valid = yield dut.mop_valid
    assert RvInstId(mop) == RvInstId.LUI
    assert valid == 1

    #yield dut.inst.eq(0x0000_0013)
    #yield Tick()
    #mop = yield dut.mop
    #valid = yield dut.mop_valid
    #assert valid == 1
    #print(RvInstId(mop), mop)
    #assert RvInstId(mop) == RvInstId.NOP

    yield dut.inst.eq(0xffffffff)
    yield Tick()
    mop = yield dut.mop
    valid = yield dut.mop_valid
    #assert RvMacroOp(mop) == RvMacroOp.LUI
    assert valid == 0

    return

class DecodeUnitTests(unittest.TestCase):
    def test_decode_elab(self):
        dut = Rv32GroupDecoder(EmberParams)
        with open("/tmp/Rv32Decoder.v", "w") as f:
            f.write(verilog.convert(dut))

    def test_decode_simple(self):
        tb = Testbench(
            Rv32GroupDecoder(EmberParams),
            tb_decode_simple,
            "tb_decode_simple"
        )
        tb.run()
        return

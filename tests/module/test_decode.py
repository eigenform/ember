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
    RvInstId = dut.p.inst.enum_type

    yield dut.inst.eq(0xffff_f0b7)
    yield Delay(1)

    alu_op = yield dut.mop.alu_op
    mop    = yield dut.mop
    mop_id = yield dut.mop_id
    valid  = yield dut.valid
    assert RvInstId(mop_id) == RvInstId.LUI
    assert AluOp(alu_op) == AluOp.ADD
    assert valid == 1

    #yield dut.inst.eq(0x0000_0013)
    #yield Tick()
    #mop = yield dut.mop
    #valid = yield dut.mop_valid
    #assert valid == 1
    #print(RvInstId(mop), mop)
    #assert RvInstId(mop) == RvInstId.NOP

    #yield dut.inst.eq(0xffffffff)
    #yield Tick()
    #mop = yield dut.mop
    #valid = yield dut.mop_valid
    ##assert RvMacroOp(mop) == RvMacroOp.LUI
    #assert valid == 0

    return

class DecodeUnitTests(unittest.TestCase):
    # NOTE: Why does this take so long to elaborate? 
    #def test_decode_elab(self):
    #    dut = Rv32GroupDecoder(EmberParams())
    #    with open("/tmp/Rv32Decoder.v", "w") as f:
    #        f.write(verilog.convert(dut, name="Rv32Decoder"))

    def test_decode_simple(self):
        tb = TestbenchComb(
            Rv32GroupDecoder(EmberParams()),
            tb_decode_simple,
            "tb_decode_simple"
        )
        tb.run()
        return




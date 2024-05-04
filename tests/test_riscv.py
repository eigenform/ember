import unittest
from ember.param import *
from ember.riscv.encoding import *
from ember.riscv.inst import *
from ember.sim.common import Testbench

from amaranth import *
from amaranth.sim import *
from amaranth.lib.enum import *
from amaranth.back import verilog, rtlil

def add_layout_case(m: Module, bits, fmt, opcode, 
                    f3=None,f7=None,f12=None,
                    rd=None,rs1=None,rs2=None,
                    imm=None):
    encoding = Const(bits, unsigned(32))
    view = View(RvEncoding(), encoding)

    if imm != None:
        imm_view = RvEncodingImmediateView(view)
        match fmt:
            case RvFormat.R: 
                pass
            case RvFormat.I: 
                i = View(StructLayout({"value": signed(12)}), imm_view.get_i_imm12())
                m.d.comb += Assert(i.value == imm)
            case RvFormat.S: 
                i = View(StructLayout({"value": signed(12)}), imm_view.get_s_imm12())
                m.d.comb += Assert(i.value == imm)
            case RvFormat.B: 
                i = View(StructLayout({"value": signed(13)}), imm_view.get_b_imm12())
                m.d.comb += Assert(i.value == imm)
            case RvFormat.U: 
                i = View(StructLayout({"value": unsigned(20)}), imm_view.get_u_imm20())
                m.d.comb += Assert(i.value == imm)
            case RvFormat.J: 
                i = View(StructLayout({"value": signed(21)}), imm_view.get_j_imm20())
                m.d.comb += Assert(i.value == imm)

    m.d.comb += Assert(view.opcode_low == 0b11, f"{bits:08x}")
    m.d.comb += Assert(view.opcode == opcode, f"{bits:08x}")
    if f3 != None: 
        m.d.comb += Assert(view.f3 == f3, f"{bits:08x}")
    if f7 != None: 
        m.d.comb += Assert(view.f7 == f7, f"{bits:08x}")
    if f12 != None: 
        m.d.comb += Assert(view.f12 == f12, f"{bits:08x}")
    if rd != None: 
        m.d.comb += Assert(view.rd == rd, f"{bits:08x}")
    if rs1 != None: 
        m.d.comb += Assert(view.rs1 == rs1, f"{bits:08x}")
    if rs2 != None: 
        m.d.comb += Assert(view.rs2 == rs2, f"{bits:08x}")


class RvEncodingUnitTests(unittest.TestCase):
    def test_imm_shape(self):
        view = RvEncodingImmediateView(C(0, 32))
        print("I", view.get_i_imm12().shape())
        print("S", view.get_s_imm12().shape())
        print("B", view.get_b_imm12().shape())
        print("U", view.get_u_imm20().shape())
        print("J", view.get_j_imm20().shape())

    def test_enc_layout_simple(self):
        m = Module()
        # 00008133: add x2,x1,x0
        add_layout_case(m, 0x0000_8133, RvFormat.R, RvOpcode.OP,
            f3=F3Op.ADD, f7=0b0000000, rd=2, rs1=1, rs2=0)

        # 7ff28293: addi x5,x5,2047
        add_layout_case(m, 0x7ff2_8293, RvFormat.I, RvOpcode.OPIMM,
            f3=F3Op.ADD, rd=5, rs1=5, imm=2047)

        # 80128293: addi x5,x5,-2047
        add_layout_case(m, 0x8012_8293, RvFormat.I, RvOpcode.OPIMM,
            f3=F3Op.ADD, rd=5, rs1=5, imm=-2047)

        # 02152023: sw x1,0x20(x10)
        add_layout_case(m, 0x0215_2023, RvFormat.S, RvOpcode.STORE,
            f3=F3Ldst.W, rs1=10, rs2=1, imm=32)

        # 02209063: bne x1,x2,20
        add_layout_case(m, 0x0220_9063, RvFormat.B, RvOpcode.BRANCH,
            f3=F3Branch.BNE, rs1=1, rs2=2, imm=32)

        # fffff0b7: lui x1,0xfffff
        add_layout_case(m, 0xffff_f0b7, RvFormat.U, RvOpcode.LUI,
            rd=1, imm=0xfffff)

        # 0000106f: jal x0,0x1000
        add_layout_case(m, 0x0000_106f, RvFormat.J, RvOpcode.JAL,
            rd=0, imm=0x1000)

        # 804ff06f: jal x0,-0xffc
        add_layout_case(m, 0x804f_f06f, RvFormat.J, RvOpcode.JAL,
            rd=0, imm=-0xffc)

        # 00000013: nop (addi x0,x0,0)
        add_layout_case(m, 0x0000_0013, RvFormat.R, RvOpcode.OPIMM,
            rd=0, rs1=0, imm=0)

        sim = Simulator(m)
        sim.run()


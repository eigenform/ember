from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
from amaranth_soc.wishbone import Signature as WishboneSignature
from amaranth_soc.wishbone import CycleType, BurstTypeExt

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.cache.l1i import *
from ember.cache.itlb import *
from ember.riscv.encoding import *
from ember.uarch.mop import ControlFlowOp

class Rv32Predecoder(Component):
    """ Predecoder for a single RV32 instruction.

    The RISC-V ISA defines ``x1`` and ``x5`` as link registers.
    Call and return instructions are qualified by the following conditions:

    - Call instructions are cases of ``JAL/JALR`` where ``rd == lr``
    - Return instructions are cases of ``JALR`` where ``(rd == 0) && (rs1 == lr)``

    """

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "inst": In(32),
            "cf_op": Out(ControlFlowOp),
            "rd": Out(5),
            "rs1": Out(5),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()
        view = View(RvEncoding(), self.inst)
        imm_view = RvEncodingImmediateView(self.inst)

        read_lr  = (view.rs1 == 1) | (view.rs1 == 5)
        write_lr = (view.rd == 1)  | (view.rd == 5)

        m.d.comb += [
            self.rd.eq(view.rd),
            self.rs1.eq(view.rs1),
        ]

        with m.Switch(view.opcode):
            with m.Case(RvOpcode.BRANCH):
                m.d.comb += self.cf_op.eq(ControlFlowOp.BRANCH)
            with m.Case(RvOpcode.JAL):
                m.d.comb += self.cf_op.eq(
                    Mux(write_lr, ControlFlowOp.CALL_DIR, 
                        ControlFlowOp.JUMP_DIR)
                )
            with m.Case(RvOpcode.JALR):
                m.d.comb += self.cf_op.eq(
                    Mux((read_lr & (view.rd == 0)), ControlFlowOp.RET, 
                        Mux(write_lr, ControlFlowOp.CALL_IND, 
                            ControlFlowOp.JUMP_IND)
                    )
                )
            with m.Default():
                m.d.comb += self.cf_op.eq(ControlFlowOp.NONE)
            

        return m




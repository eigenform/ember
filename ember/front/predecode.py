from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
from amaranth_soc.wishbone import Signature as WishboneSignature
from amaranth_soc.wishbone import CycleType, BurstTypeExt

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.riscv.encoding import *
from ember.uarch.mop import ControlFlowOp
from ember.uarch.fetch import *

class PredecodeInfo(StructLayout):
    """ A predecoded RISC-V instruction. 

    Fields
    ======
    ill:
        The encoding for this instruction is invalid/illegal.
    cf_op: :class:`ControlFlowOp`
        Control flow operation associated with this instruction.
    rd: 
        Architectural destination register RD
    rs1: 
        Architectural source register RS1
    imm:
        Extracted immediate value
    tgt:
        Computed target address
    tgt_valid:
        The target address is valid. 


    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "ill": unsigned(1),
            "is_cf": unsigned(1),
            "cf_op": ControlFlowOp,
            "rd": unsigned(5),
            "rs1": unsigned(5),
            "imm": RvImmData(),
            "tgt": p.vaddr,
            "tgt_valid": unsigned(1),
        })

class PredecodeRequest(Signature):
    """ A request to pre-decode an L1I cacheline. 

    Members
    =======
    valid:
        This request is valid
    vaddr:
        The *program counter* associated with this request
    ftq_idx:
        The FTX index associated with this request
    cline:
        L1I cache line data

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "ftq_idx": Out(FTQIndex(p)),
            "cline": Out(p.l1i.line_layout),
        })

class PredecodeResponse(Signature):
    """ A pre-decoded L1I cacheline.

    Members
    =======
    valid:
        This response is valid
    vaddr:
        Program counter associated with this response
    ftq_idx:
        FTQ index associated with this response
    info:
        Predecode info [for each word in the cacheline]
    info_valid:
        Bitmask for words in the cacheline that have been predecoded

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "ftq_idx": Out(FTQIndex(p)),
            "info": Out(PredecodeInfo(p)).array(p.l1i.line_depth),
            "info_valid": Out(1).array(p.l1i.line_depth),
        })


class Rv32Predecoder(Component):
    """ Predecoder for a single RV32 instruction.

    The RISC-V ISA defines ``x1`` and ``x5`` as link registers.
    Call and return instructions are qualified by the following conditions:

    - Call instructions are cases of ``JAL/JALR`` where ``rd == lr``
    - Return instructions are cases of ``JALR`` where ``(rd == 0) && (rs1 == lr)``

    Ports
    =====
    inst:
        Input RISC-V instruction encoding
    inst_valid:
        Input is valid
    pc: 
        Program counter value for this instruction
    info:
        Predecoded output for this instruction
    info_valid:
        Predecoded output is valid

    """

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "inst": In(32),
            "inst_valid": In(1),
            "pc": In(param.rv.xlen),
            "info": Out(PredecodeInfo(param)),
            "info_valid": Out(1),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        ill   = Signal(1)
        is_cf = Signal(1)
        cf_op = Signal(ControlFlowOp)
        rd    = Signal(5)
        rs1   = Signal(5)
        imm   = Signal(RvImmData())
        simm  = Signal(32)

        tgt_pc_valid = Signal(1)
        tgt_pc = Signal(self.p.vaddr)

        enc_view     = View(RvEncoding(), self.inst)
        enc_imm_view = RvEncodingImmediateView(self.inst)
        imm_view     = RvImmDataView(imm)

        read_lr  = (enc_view.rs1 == 1) | (enc_view.rs1 == 5)
        write_lr = (enc_view.rd == 1)  | (enc_view.rd == 5)

        m.d.comb += [
            rd.eq(enc_view.rd),
            rs1.eq(enc_view.rs1),
            # Take this as a hint that the encoding is invalid
            ill.eq(enc_view.opcode_low != 0b11),
        ]

        # NOTE: Presumably the cost of a 32-bit adder here is *not* negligible.
        # Just something to keep in mind for later.
        #
        # 1. Determine whether or not this is a control-flow instruction.
        # 2. Extract and sign-extend the immediate value.
        # 3. For direct jump/branch ops, compute the target address.
        #
        with m.Switch(enc_view.opcode):
            with m.Case(RvOpcode.BRANCH):
                m.d.comb += [
                    is_cf.eq(1),
                    cf_op.eq(ControlFlowOp.BRANCH),
                    imm.eq(enc_imm_view.get_b_imm12()),
                    simm.eq(imm_view.b_sext32()),
                    tgt_pc.eq(self.pc + simm),
                    tgt_pc_valid.eq(1),
                ]
            with m.Case(RvOpcode.JAL):
                m.d.comb += [ 
                    is_cf.eq(1),
                    cf_op.eq(Mux(write_lr, 
                        ControlFlowOp.CALL_DIR, 
                        ControlFlowOp.JUMP_DIR
                    )),
                    imm.eq(enc_imm_view.get_j_imm20()),
                    simm.eq(imm_view.j_sext32()),
                    tgt_pc.eq(self.pc + simm),
                    tgt_pc_valid.eq(1),
                ]
            with m.Case(RvOpcode.JALR):
                m.d.comb += [
                    is_cf.eq(1),
                    cf_op.eq(Mux((read_lr & (enc_view.rd == 0)), 
                        ControlFlowOp.RET, 
                        Mux(write_lr, ControlFlowOp.CALL_IND, ControlFlowOp.JUMP_IND))
                    ),
                    imm.eq(enc_imm_view.get_i_imm12()),
                    simm.eq(imm_view.i_sext32()),
                    tgt_pc.eq(0),
                    tgt_pc_valid.eq(0),
                ]
            with m.Default():
                m.d.comb += [
                    is_cf.eq(0),
                    cf_op.eq(ControlFlowOp.NONE),
                    imm.eq(0),
                    simm.eq(0),
                    tgt_pc.eq(0),
                    tgt_pc_valid.eq(0),
                ]

        # Drive outputs
        valid = self.inst_valid
        m.d.comb += [
            self.info_valid.eq(valid),
            self.info.ill.eq(Mux(valid, ill, 0)),
            self.info.is_cf.eq(Mux(valid, is_cf, 0)),
            self.info.cf_op.eq(Mux(valid, cf_op, ControlFlowOp.NONE)),
            self.info.rd.eq(Mux(valid, rd, 0)),
            self.info.rs1.eq(Mux(valid, rs1, 0)),
            self.info.imm.eq(Mux(valid, imm, 0)),
            self.info.tgt.eq(Mux(valid, tgt_pc, 0)),
            self.info.tgt_valid.eq(Mux(valid, tgt_pc_valid, 0)),
        ]
            

        return m



class PredecodeUnit(Component):
    """ Pre-decodes an L1I cacheline in an attempt to extract information 
    about control-flow instructions.

    Each word in an L1I cacheline has a dedicated predecoder which extracts
    the following pieces of information: 

    - Hints about whether or not the RISC-V encoding is valid
    - Whether or not the instruction is a control-flow instruction
    - The specific type of control-flow operation
    - Any relevant architectural register operands
    - A sign-extended 32-bit immediate value 

    1. A request arrives from the IFU pipe with a fetched L1I cacheline.
    2. Depending on the offset into the line (given by the program counter),
       drive instruction bytes to the predecoders. 
    3. Predecode data is available on the next cycle. 


    """

    def __init__(self, param: EmberParams):
        self.p = param
        self.width = param.l1i.line_depth
        sig = Signature({
            "req": In(PredecodeRequest(param)),
            "resp": Out(PredecodeResponse(param)),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        # Instantiate a predecoder for each word in a cacheline. 
        info = Array(Signal(PredecodeInfo(self.p)) for _ in range(self.width))
        info_valid = Array(Signal() for _ in range(self.width))
        pd = [ Rv32Predecoder(self.p) for _ in range(self.width) ]
        for idx in range(self.width):
            m.submodules[f"predecoder{idx}"] = pd[idx]
            m.d.comb += info[idx].eq(pd[idx].info)
            m.d.comb += info_valid[idx].eq(pd[idx].info_valid)

        # Use the low bits of the associated program counter to obtain the 
        # index of the first relevant word in the cacheline
        start_idx = (self.req.vaddr.fetch_off) >> 2

        # Default assignments
        #m.d.comb += [ pd[idx].inst_valid.eq(0) for idx in range(self.width) ]
        #m.d.comb += [ pd[idx].inst.eq(0) for idx in range(self.width) ]

        # Drive each valid word in the cacheline to a predecoder along with 
        # the appropriate program counter value for the word
        for idx in range(self.width):
            word_pc = Cat(C(idx*4, 5), self.req.vaddr.fetch_blk)
            with m.If(idx >= start_idx):
                m.d.comb += pd[idx].pc.eq(word_pc)
                m.d.comb += pd[idx].inst.eq(self.req.cline[idx])
                m.d.comb += pd[idx].inst_valid.eq(1)
            with m.Else():
                m.d.comb += pd[idx].pc.eq(0)
                m.d.comb += pd[idx].inst.eq(0)
                m.d.comb += pd[idx].inst_valid.eq(0)

        # Capture output from the predecoders. 
        # Output response is available on the next cycle. 
        for idx in range(self.width):
            m.d.sync += [
                self.resp.info_valid[idx].eq(info_valid[idx]),
                self.resp.info[idx].ill.eq(info[idx].ill),
                self.resp.info[idx].cf_op.eq(info[idx].cf_op),
                self.resp.info[idx].rd.eq(info[idx].rd),
                self.resp.info[idx].rs1.eq(info[idx].rs1),
                self.resp.info[idx].imm.eq(info[idx].imm),
            ]
        m.d.sync += [
            self.resp.valid.eq(self.req.valid),
            self.resp.vaddr.eq(self.req.vaddr),
            self.resp.ftq_idx.eq(self.req.ftq_idx),
        ]


        return m







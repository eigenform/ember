
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *

from ember.riscv.inst import *
from ember.riscv.encoding import *
from ember.uarch.mop import *
from ember.param import *

class Rv32GroupDecoder(Component):
    """ A decoder for a single RISC-V instruction. 

    - Maps a single RV32 instruction onto a macro-op
    - Extracts immediate data
    - Extracts source/destination register operands

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "inst": In(32),

            "mop": Out(EmberMop.layout),
            "mop_id": Out(param.inst.enum_type),
            "rd": Out(5),
            "rs1": Out(5),
            "rs2": Out(5),
            "imm": Out(RvImmData()),
            "valid": Out(1),
        })
        super().__init__(signature)
        return

    def elaborate(self, platform):
        m = Module()
        view = View(RvEncoding(), self.inst)
        enc_imm_view = RvEncodingImmediateView(self.inst)

        imm = Signal(RvImmData())
        mop = Signal(EmberMop.layout)
        mop_id = Signal(self.p.inst.enum_type)

        m.d.comb += [
            self.rd.eq(view.rd),
            self.rs1.eq(view.rs1),
            self.rs2.eq(view.rs2),
            self.mop.eq(mop),
            self.mop_id.eq(mop_id),
            self.imm.eq(imm),
        ]

        # Generate decoder cases (mapping instructions to macro-ops).
        # Since masks might have dont-care bits, we should probably order
        # these by the number of defined bits in the mask. 
        decoder_cases = {}
        for name, op in self.p.inst.items_by_specificity():
            decoder_cases[name] = { 
                "mask": str(op.match()),
                "mop":  self.p.mops.get_const_by_name(name),
                "id":   self.p.inst.get_inst_id_by_name(name),
            }

        # FIXME: This doesn't do matching in parallel. 
        with m.Switch(self.inst):
            for name, case in decoder_cases.items():
                with m.Case(case["mask"]):
                    m.d.comb += [
                        mop.eq(case["mop"]),
                        mop_id.eq(case["id"]),
                        self.valid.eq(1),
                    ]
            with m.Default():
                m.d.comb += [
                    mop.eq(EmberMop(RvFormat.R).as_const()),
                    mop_id.eq(0),
                    self.valid.eq(0),
                ]

        # FIXME: You should probably do this in parallel too
        with m.Switch(mop.fmt):
            with m.Case(RvFormat.R):
                m.d.comb += imm.eq(0)
            with m.Case(RvFormat.I):
                m.d.comb += imm.eq(enc_imm_view.get_i_imm12())
            with m.Case(RvFormat.S):
                m.d.comb += imm.eq(enc_imm_view.get_s_imm12())
            with m.Case(RvFormat.B):
                m.d.comb += imm.eq(enc_imm_view.get_b_imm12())
            with m.Case(RvFormat.U):
                m.d.comb += imm.eq(enc_imm_view.get_u_imm20())
            with m.Case(RvFormat.J):
                m.d.comb += imm.eq(enc_imm_view.get_j_imm20())

        return m

class DecodeRequest(Signature):
    """ A request to decode a single RISC-V instruction.
    """
    def __init__(self, p: EmberParams, width: int): 
        super().__init__({
            "valid": Out(1),
            "ftq_idx": Out(p.ftq.index_shape),
            "inst": Out(32).array(width),
        })

class DecodeResponse(Signature):
    def __init__(self, p: EmberParams, width: int): 
        super().__init__({
            "valid": Out(1),
            "ftq_idx": Out(p.ftq.index_shape),
            "inst": Out(32).array(width),
        })

class DecodeUnit(Component):
    """ Decodes a packet of RISC-V instructions. 

    """
    def __init__(self, param: EmberParams):
        self.p = param
        self.width = param.decode.width
        super().__init__(Signature({
            "req": In(DecodeRequest(param, self.width)),
            "resp": Out(DecodeResponse(param, self.width)),
        }))

    def elaborate(self, platform):
        m = Module()

        dec = [ Rv32GroupDecoder(self.p) for _ in range(self.width) ]
        for idx in range(self.width):
            m.submodules[f"decoder{idx}"] = dec[idx]

        return m 


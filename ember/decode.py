
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *

from ember.riscv.inst import *
from ember.riscv.encoding import *
from ember.uarch.mop import *
from ember.param import *

class DecodeRequest(Signature):
    """ Request to decode a single instruction. """
    def __init__(self, param: EmberParams):
        super().__init__({
            "inst": Out(32),
        })

class DecodeResponse(Signature):
    def __init__(self, param: EmberParams):
        super().__init__({
            "mop": Out(EmberMop.layout),
            "mop_id": Out(param.inst.enum_type),
            "rd": Out(5),
            "rs1": Out(5),
            "rs2": Out(5),
            "valid": Out(1),
        })


class Rv32GroupDecoder(Component):
    """ A decoder that maps a single RV32 instruction onto a macro-op. 



    .. warning::
        For now, this decoder probably synthesizes into many cascading levels
        of logic. This is probably fine for simple testing, but the delay on 
        actual hardware is probably too great to be clocked very high. 

        Instead, you probably want to check all cases in parallel, priority 
        encode the resulting bits, and then use the index to access a table of 
        macro-op constants. 

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "req": In(DecodeRequest(param)),
            "resp": Out(DecodeResponse(param)),
        })
        super().__init__(signature)
        return

    def elaborate(self, platform):
        m = Module()
        view = View(RvEncoding(), self.req.inst)

        m.d.comb += [
            self.resp.rd.eq(view.rd),
            self.resp.rs1.eq(view.rs1),
            self.resp.rs2.eq(view.rs2),
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
        with m.Switch(self.req.inst):
            for name, case in decoder_cases.items():
                with m.Case(case["mask"]):
                    m.d.comb += [
                        self.resp.mop.eq(case["mop"]),
                        self.resp.mop_id.eq(case["id"]),
                        self.resp.valid.eq(1),
                    ]
            with m.Default():
                m.d.comb += [
                    self.resp.mop.eq(EmberMop(RvFormat.R).as_const()),
                    self.resp.mop_id.eq(0),
                    self.resp.valid.eq(0),
                ]
        return m



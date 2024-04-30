
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.riscv import *
from ember.riscv.encoding import *

class DecodeRequest(Signature):
    def __init__(self):
        super().__init__({
            "bits": Out(unsigned(32)),
        })

class Rv32Decoder(Component):
    def __init__(self):
        signature = Signature({
            "inst": In(unsigned(32)),
            "mop": Out(RvMacroOp),
        })
        super().__init__(signature)
        return
    def elaborate(self, platform):
        m = Module()

        enc = View(RvEncoding(), self.inst)
        mop = Signal(RvMacroOp)


        m.d.sync += mop.eq(
        )

        return m



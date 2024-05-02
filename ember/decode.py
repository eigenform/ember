
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
    def __init__(self):
        super().__init__({
            "bits": Out(unsigned(32)),
        })




class Rv32GroupDecoder(Component):
    """ A decoder for an arbitrary group of RV32 instructions.

    .. note:: 
        The logic here can probably be minimized.
    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "inst": In(unsigned(32)),
            "uop": Out(EmberMop.layout),
        })
        super().__init__(signature)
        return

    def elaborate(self, platform):
        m = Module()
        enc = View(RvEncoding(), self.inst)

        uop = Signal(EmberMop.layout)

        with m.Switch(self.inst):
            for (idx, (name, op)) in enumerate(self.p.decode.inst_group.members.items()):
                with m.Case(str(op.match())):
                    m.d.comb += self.uop.eq(self.p.decode.mop_group.members[name].as_const())
            with m.Default():
                m.d.comb += self.uop.eq(EmberMop(RvFormat.R).as_const())
 
        # A bit for each instruction in the group
        #arr = Signal(self.group.id_shape_onehot())
        #for (idx, (name, op)) in enumerate(self.group.members_by_specificity()):
        #    m.d.comb += arr[idx].eq(self.inst.matches(str(op.match())))
        #m.submodules.encoder = encoder = Encoder(len(self.group.members))
        #encoder_valid = ~encoder.n
        #encoder_idx   = encoder.o
        #m.d.comb += [
        #    #Print(Format("{:0{width}b}", arr, width=len(self.group.members))),
        #    encoder.i.eq(Cat(*arr)),
        #]

        



        m.d.sync += [
            #self.mop.eq(encoder_idx),
            #self.mop_valid.eq(encoder_valid)
        ]

        return m



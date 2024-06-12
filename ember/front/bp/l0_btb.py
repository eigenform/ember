from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
from amaranth.utils import ceil_log2, exact_log2

from ember.common import *
from ember.common.pipeline import *
from ember.common.coding import ChainedPriorityEncoder
from ember.param import *
from ember.front.predecode import *
from ember.uarch.fetch import *

class L0BTBEntry(StructLayout):
    def __init__(self, p: EmberParams):
        super().__init__({
            "idx": unsigned(exact_log2(p.vaddr.num_off_bits)),
            "info": PredecodeInfo(p),
        })

class L0BTBReadPort(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
        })


class L0BranchTargetBuffer(Component):
    """ Fully-associative Branch Target Buffer (BTB). 

    """
    def __init__(self, param: EmberParams):
        self.p = param
        self.depth = 8
        super().__init__(Signature({
        }))

    def elaborate(self, platform):
        m = Module()

        tag_arr = Array(Signal(self.p.bp.l0_btb_tag_shape) for i in range(self.depth))
        data_arr = Array(Signal(L0BTBEntry(self.p)) for i in range(self.depth))
        valid_arr = Array(Signal() for i in range(self.depth))
        match_arr = Array(
            Signal(name=f"match_arr{i}") for i in range(self.depth)
        )



        return m



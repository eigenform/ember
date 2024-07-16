
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from ember.common.mem import *
from ember.uarch.front import *
from ember.param import *

class BankedL1ICache(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        super().__init__(Signature({
        }))

    def elaborate(self, platform):
        m = Module()
        data_banks = m.submodules.tag_banks = \
                BankedMemory(4, 4, L1ICacheline(self.p))
        tag_banks  = m.submodules.tag_banks = \
                BankedMemory(4, 4, L1ITag())
        return m 


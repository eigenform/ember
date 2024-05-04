from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth.utils import log2_int, exact_log2

from ember.axi import *


class IBusControllerAXI(Component):
    def __init__(self, cfg: AXIConfig): 
        self.cfg = cfg
        signature = Signature({
            "axi": Out(AXIPort(cfg)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        return m




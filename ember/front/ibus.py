from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth.utils import log2_int, exact_log2

from ember.param import *
from ember.uarch.front import *
from ember.axi import *

class MockIBusController(Component):
    """ Temporary logic for moving instruction bytes into the core. 

    This is only intended to be used with testbenches. 
    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "addr": Out(32),
            "data": In(L1ICacheline(param)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        return m




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




#!/usr/bin/env python3

from amaranth import *
from amaranth.sim import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.sim.fakeram import *
from ember.param import *
from ember.core import *

#class EmbrTest(Component):
#    def __init__(self, param: EmberParams):
#        self.p = param
#        signature = Signature({
#            "ibus": Out(FakeRamInterface(4)),
#        })
#        super().__init__(signature)
#    def elaborate(self, platform): 
#        m = Module()
#        m.submodules.fetch = fetch = FetchUnit(self.p)
#        m.submodules.decode = decode = FetchUnit(self.p)
#
#        return m


#dut = EmberCore(EmberParams())
#
#
#ram = FakeRam(0x0000_1000)
#with open("./rv32/simple.bin", "rb") as f:
#    ram_data = bytearray(f.read())
#
#ram.write_bytes(0x0000_0000, ram_data)

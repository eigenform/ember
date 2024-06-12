#!/usr/bin/env python3

from amaranth import *
from amaranth.sim import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.sim.fakeram import *
from ember.param import *
from ember.core import *
from ember.decode import *

class EmbrTest(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
        })

        super().__init__(signature)
    def elaborate(self, platform): 
        m = Module()

        decoder = [ Rv32Decoder(self.p) for _ in range(4) ]

        return m


#dut = EmberCore(EmberParams())
#
#
#ram = FakeRam(0x0000_1000)
#with open("./rv32/simple.bin", "rb") as f:
#    ram_data = bytearray(f.read())
#
#ram.write_bytes(0x0000_0000, ram_data)

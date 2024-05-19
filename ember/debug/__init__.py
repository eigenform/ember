
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from ember.param import *

#class DebugCounter(Elaboratable):
#    def __init__(self, name: str, width: int):
#        self.name = name
#        self.en  = Signal()
#        self.out = Signal(width)
#        self.rst = Signal()
#        self.ov  = Signal()
#
#    def elaborate(self, platform):
#        m = Module()
#        next_val = self.out + 1
#        next_ov  = (next_val == 0)
#        m.d.sync += self.ov.eq(next_ov)
#        with m.If(self.en & ~next_ov):
#            m.d.sync += self.out.eq(next_val)
#        with m.If(self.rst):
#            m.d.sync += self.out.eq(0)
#            m.d.sync += self.ov.eq(0)
#        return m


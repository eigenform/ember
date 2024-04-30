from amaranth import *
from amaranth.hdl.ast import ShapeCastable
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *

class Valid(Signature):
    def __init__(self, layout):
        super().__init__({
            "bits": Out(layout),
            "valid": Out(1),
        })

class Decoupled(Signature):
    def __init__(self, layout):
        super().__init__({
            "bits": Out(layout),
            "valid": Out(1),
            "ready": In(1),
        })

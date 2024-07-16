
from abc import abstractmethod, ABCMeta, ABC

from amaranth import *
from amaranth import ShapeLike
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2
from ember.param.top import EmberParams

__all__ = [
    "EmberParams",
    "EmberComponent",
]

class EmberComponent(Component):
    def __init__(self, p: EmberParams, 
                 signature_members: dict):
        self.p = p
        super().__init__(Signature(signature_members))


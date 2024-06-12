from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *
from amaranth.utils import ceil_log2, exact_log2


class PipelinePacket(Signature): 
    def __init__(self, width: int, data_name: str, data_layout: Layout): 
        members = {}
        members[data_name] = Out(data_layout).array(width)
        super().__init__(members)

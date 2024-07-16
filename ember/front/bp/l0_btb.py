from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
from amaranth.utils import ceil_log2, exact_log2

from ember.common import *
from ember.common.pipeline import *
from ember.common.coding import ChainedPriorityEncoder, EmberPriorityEncoder
from ember.param import *
from ember.front.predecode import *
from ember.uarch.front import *

class L0BTBEntry(StructLayout):
    """ L0 BTB entry.
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            # Predecoded information
            "info": PredecodeInfo(p.vaddr),
            # Previously-selected way
            "way": unsigned(exact_log2(p.l1i.num_ways)),
        })

class L0BTBTag(Shape):
    """ L0 BTB tag bits. 
    """
    def __init__(self, vaddr: VirtualAddress): 
        super().__init__(width=vaddr.num_off_bits)



class L0BTBReadPort(Signature):
    """ L0 BTB read port. 
    """

    class Request(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "pc": Out(p.vaddr),
                "valid": Out(1)
            })
    class Response(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "data": Out(L0BTBEntry(p)),
                "valid": Out(1)
            })

    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(self.Request(p)),
            "resp": In(self.Response(p)),
        })

class L0BTBWritePort(Signature):
    """ L0 BTB write port. 
    """
    class Request(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "pc": Out(p.vaddr),
                "data": Out(L0BTBEntry(p)),
                "valid": Out(1),
            })
    class Response(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1)
            })

    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(self.Request(p)),
            "resp": In(self.Response(p)),
        })




class L0BranchTargetBuffer(Component):
    """ Fully-associative Branch Target Buffer (BTB). 

    """
    def __init__(self, param: EmberParams):
        self.p = param
        self.depth = param.bp.l0_btb.depth
        super().__init__(Signature({
            "rp": In(L0BTBReadPort(param)),
            "wp": In(L0BTBWritePort(param)),
        }))

    def elaborate(self, platform):
        m = Module()

        pc = Signal(30)
        m.d.comb += pc.eq(self.rp.req.pc.bits[2:])

        # FIXME: For now, just take the low bits as the tag
        tag = Signal(L0BTBTag(self.p.vaddr))
        m.d.comb += tag.eq(self.rp.req.pc.bits)

        tag_arr = Array(
            Signal(L0BTBTag(self.p.vaddr)) for i in range(self.depth)
        )
        data_arr = Array(
            Signal(L0BTBEntry(self.p)) for i in range(self.depth)
        )
        valid_arr = Array(Signal() for i in range(self.depth))
        match_arr = Array(
            Signal(name=f"match_arr{i}") for i in range(self.depth)
        )

        with m.If(self.wp.req.valid):
            pass

        for idx in range(self.depth):
            hit = (valid_arr[idx] & (tag_arr[idx] == tag))
            m.d.comb += match_arr[idx].eq(hit)

        
        enc = m.submodules.enc = EmberPriorityEncoder(self.depth)
        m.d.comb += enc.i.eq(Cat(*match_arr))



        return m



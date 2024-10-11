from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.nfp import *
from ember.uarch.front import *

class ControlFlowMapReadPort(Signature):
    class Request(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "pc": Out(p.vaddr),
            })
    class Response(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                #"entry": Out(CFMEntry(p)),
                "pc": Out(p.vaddr),
                "blocks": Out(p.fblk_size_shape),
            })
    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(ControlFlowMapReadPort.Request(p)),
            "resp": In(ControlFlowMapReadPort.Response(p)),
        })

class ControlFlowMapWritePort(Signature):
    class Request(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "pc": Out(p.vaddr),
                "entry": Out(FetchBlockMetadata(p)),
            })
    class Response(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
            })
    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(ControlFlowMapWritePort.Request(p)),
            "resp": In(ControlFlowMapWritePort.Response(p)),
        })


class FetchBlockExit(Enum, shape=4):
    NONE     = 0b0000
    # Fall through to the next-sequential block
    FALLTHRU = 0b0001
    # Unconditionally link to a different block
    LINK     = 0b0010

class FetchBlockMetadata(StructLayout):
    def __init__(self, p: EmberParams):
        super().__init__({
            "entry_pc": p.vaddr,
            "blocks": p.fblk_size_shape,
            "next_pc": p.vaddr,
        })


class L0ControlFlowMap(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        super().__init__(Signature({
            "rp": In(ControlFlowMapReadPort(param)),
            "wp": In(ControlFlowMapReadPort(param)),
        }))

    def elaborate(self, platform):
        m = Module()

        data_arr = Array([ 
            Signal(FetchBlockMetadata(self.p))
            for _ in range(4)
        ])
        valid_arr = Array([ Signal(name=f"valid_arr{idx}", init=0) for idx in range(4) ])

        m.submodules.enc = enc = EmberPriorityEncoder(4)
        match_arr = Array([ Signal(name=f"match_arr{idx}") for idx in range(4) ])

        m.d.comb += enc.i.eq(Cat(*match_arr))
        hit = enc.valid
        hit_idx = enc.o

        m.d.comb += [ match_arr[idx].eq(0) for idx in range(4) ]
        with m.If(self.rp.req.valid):
            for idx in range(4):
                m.d.comb += [
                    match_arr[idx].eq(
                        valid_arr[idx] & 
                        (self.rp.req.pc == data_arr[idx].entry_pc)
                    ),
                ]

        hit_entry = Signal(FetchBlockMetadata(self.p))
        m.d.comb += [
            hit_entry.eq(Mux(hit, data_arr[hit_idx], 0)),
        ]

        m.d.comb += [
            self.rp.resp.valid.eq(self.rp.req.valid & hit),
            self.rp.resp.pc.eq(hit_entry.next_pc),
            self.rp.resp.blocks.eq(hit_entry.blocks),
        ]



        return m







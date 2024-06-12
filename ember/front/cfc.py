from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.ftq import FTQAllocRequest, FTQStatusBus
from ember.front.nfp import *
from ember.uarch.fetch import *

class ControlFlowSource(Enum):
    """ The source type for a control-flow request. 

    Values
    ======
    NONE: 
        No source
    L0_PREDICT:
        L0 (next-fetch) prediction
    L1_PREDICT: 
        L1 prediction
    REDIR_PREDECODE: 
        L0 prediction corrected from predecode

    """
    NONE       = 0 
    L0_PREDICT = 1
    L1_PREDICT = 2
    REDIR_PREDECODE = 3

class ControlFlowRequest(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "pc": Out(p.vaddr),
            "src": Out(ControlFlowSource),
            "parent_ftq_idx": Out(FTQIndex(p)),
        })


class ControlFlowController(Component):
    """ Collects control-flow requests from different parts of the machine 
    and sends them to the FTQ. 

    .. note:
        This is mostly temporary [hacky] logic until we figure out exactly how 
        we want to handle things.

    Ports
    =====
    dbg:
        Incoming *architectural* control-flow request [from off-core]
    redir:
        Incoming *architectural* control-flow request [from mid-core]
    bpu:
        Incoming *speculative* control-flow request [from the BPU]

    """
    def __init__(self, param: EmberParams):
        self.p = param
        super().__init__(Signature({
            "dbg": In(ControlFlowRequest(param)),
            "redir": In(ControlFlowRequest(param)),
            "bpu": In(ControlFlowRequest(param)),

            "ftq_sts": In(FTQStatusBus(param)),
            "alloc_req": Out(FTQAllocRequest(param)),
        }))

    def elaborate(self, platform):
        m = Module()

        nfp = m.submodules.nfp = NextFetchPredictor(self.p)

        r_pc = Signal(32, init=0x0000_0000)
        r_predicted = Signal(1, init=0)

        npc = Signal(32)
        npc_predicted = Signal()
        with m.If(self.dbg.valid):
            m.d.comb += npc.eq(self.dbg.pc)
            m.d.comb += npc_predicted.eq(0)
        with m.Else():
            m.d.comb += npc.eq(r_pc)
            m.d.comb += npc_predicted.eq(r_predicted)

        m.d.comb += [
            nfp.req.pc.eq(npc),
        ]

        # Output to the FTQ
        with m.If(self.ftq_sts.ready):
            m.d.sync += [
                self.alloc_req.valid.eq(1),
                self.alloc_req.vaddr.eq(npc),
                self.alloc_req.passthru.eq(1),
            ]
        with m.Else():
            m.d.sync += [
                self.alloc_req.valid.eq(0),
                self.alloc_req.vaddr.eq(0),
                self.alloc_req.passthru.eq(0),
            ]

        with m.If(self.ftq_sts.ready):
            m.d.sync += [
                r_pc.eq(nfp.resp.npc),
                r_predicted.eq(nfp.resp.npc),
            ]

        return m

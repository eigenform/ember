from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.ftq import FTQAllocRequest, FTQStatusBus
from ember.front.nfp import *
from ember.uarch.front import *

class ControlFlowRequest(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "pc": Out(p.vaddr),
            "parent_ftq_idx": Out(p.ftq.index_shape),
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
    ftq_sts:
        FTQ allocation status
    alloc_req:
        FTQ allocation request

    """
    def __init__(self, param: EmberParams):
        self.p = param
        super().__init__(Signature({
            "dbg":       In(ControlFlowRequest(param)),
            "ftq_sts":   In(FTQStatusBus(param)),
            "alloc_req": Out(FTQAllocRequest(param)),
        }))

    def elaborate(self, platform):
        m = Module()

        nfp = m.submodules.nfp = NextFetchPredictor(self.p)
        r_nfp_pc    = Signal(32, init=0x0000_0000)
        r_nfp_valid = Signal(1, init=0)

        # Select which program counter value is sent to the FTQ.
        sel_pc    = Signal(32)
        sel_pred  = Signal(1)
        sel_valid = Signal(1)
        with m.If(self.dbg.valid):
            m.d.comb += [
                sel_pc.eq(self.dbg.pc),
                sel_pred.eq(0),
                sel_valid.eq(1),
            ]
        with m.Elif(r_nfp_valid):
            m.d.comb += [
                sel_pc.eq(r_nfp_pc),
                sel_pred.eq(1),
                sel_valid.eq(1),
            ]
        with m.Else():
            m.d.comb += [
                sel_pc.eq(0),
                sel_pred.eq(0),
                sel_valid.eq(0),
            ]

        # Send the selected program counter value to the NFP.
        m.d.comb += [
            nfp.req.pc.eq(sel_pc),
            nfp.req.valid.eq(sel_valid),
        ]
        # Output from the NFP is available on the next cycle
        m.d.sync += [
            r_nfp_pc.eq(nfp.resp.pc),
            r_nfp_valid.eq(nfp.resp.valid),
        ]


        # Capture the selected program counter value from this cycle
        r_pc    = Signal(32, init=0x0000_0000)
        r_pred  = Signal(init=0)
        r_valid = Signal(init=0)
        m.d.sync += [
            r_pc.eq(sel_pc),
            r_pred.eq(sel_pred),
            r_valid.eq(sel_valid),
        ]

        # Send a request to the FTQ
        with m.If(self.ftq_sts.ready):
            m.d.sync += [
                self.alloc_req.valid.eq(1),
                self.alloc_req.vaddr.eq(sel_pc),
                self.alloc_req.passthru.eq(1),
            ]
        with m.Else():
            m.d.sync += [
                self.alloc_req.valid.eq(0),
                self.alloc_req.vaddr.eq(0),
                self.alloc_req.passthru.eq(0),
            ]


        #npc = Signal(32)
        #npc_predicted = Signal()
        #with m.If(self.dbg.valid):
        #    m.d.comb += npc.eq(self.dbg.pc)
        #    m.d.comb += npc_predicted.eq(0)
        #with m.Else():
        #    m.d.comb += npc.eq(r_pc)
        #    m.d.comb += npc_predicted.eq(r_predicted)

        #m.d.comb += [
        #    nfp.req.pc.eq(npc),
        #]

        ## Output to the FTQ
        #with m.If(self.ftq_sts.ready):
        #    m.d.sync += [
        #        self.alloc_req.valid.eq(1),
        #        self.alloc_req.vaddr.eq(npc),
        #        self.alloc_req.passthru.eq(1),
        #    ]
        #with m.Else():
        #    m.d.sync += [
        #        self.alloc_req.valid.eq(0),
        #        self.alloc_req.vaddr.eq(0),
        #        self.alloc_req.passthru.eq(0),
        #    ]

        #with m.If(self.ftq_sts.ready):
        #    m.d.sync += [
        #        r_pc.eq(nfp.resp.npc),
        #        r_predicted.eq(nfp.resp.npc),
        #    ]

        return m

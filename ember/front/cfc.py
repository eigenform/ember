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
    """ Collects control-flow requests from different parts of the machine and 
    sends them to the FTQ. 

    .. note:
        This is mostly temporary [hacky] logic until we figure out exactly how 
        we want to handle things.

    There should be three different cases we need to handle:

    1. We are receiving a valid architectural CFR. 
    2. We are receiving a valid speculative CFR from somewhere in the 
       branch prediction pipeline.
    3. We are generating a speculative CFR with output from the next-fetch
       predictor. 

    There should also be three different cases for allocating an FTQ entry:

    1. If we've received an architectural CFR, allocate for it
    2. If we've received a speculative CFR, allocate for it
    3. If the next-fetch predictor output from the previous cycle is 
       valid, allocate for it. 

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

        # These wires are used to build an FTQ allocation request
        sel_pc    = Signal(32)
        sel_pred  = Signal(1)
        sel_valid = Signal(1)
        sel_passthru = Signal(1)
        m.d.comb += [
            sel_pc.eq(0),
            sel_pred.eq(0),
            sel_valid.eq(0),
            sel_passthru.eq(0),
        ]

        # Case 1. If the NFP output from the previous cycle is valid
        with m.If(r_nfp_valid):
            m.d.comb += [
                sel_pc.eq(r_nfp_pc),
                sel_pred.eq(1),
                sel_valid.eq(1),
                sel_passthru.eq(1),
            ]
        # Case 2. We're receiving an architectural CFR
        with m.If(self.dbg.valid):
            m.d.comb += [
                sel_pc.eq(self.dbg.pc),
                sel_pred.eq(0),
                sel_valid.eq(1),
                sel_passthru.eq(1),
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

        # Capture the selected program counter value from this cycle.
        # These registers hold information from the previous CFR.
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
                self.alloc_req.valid.eq(sel_valid),
                self.alloc_req.vaddr.eq(sel_pc),
                self.alloc_req.passthru.eq(sel_passthru),
            ]
        with m.Else():
            m.d.sync += [
                self.alloc_req.valid.eq(0),
                self.alloc_req.vaddr.eq(0),
                self.alloc_req.passthru.eq(0),
            ]

        return m

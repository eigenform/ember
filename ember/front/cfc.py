from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.ftq import FTQAllocRequest, FTQStatusBus
from ember.front.nfp import *
from ember.front.cfm import *
from ember.front.bp.rap import *
from ember.uarch.front import *

class CFRSource(Enum, shape=2):
    NONE = 0
    RESTEER = 1
    DEBUG = 2
    PRED0 = 3

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
            "resteer_req": In(ResteerRequest(param)),
            "ftq_sts":   In(FTQStatusBus(param)),
            "alloc_req": Out(FTQAllocRequest(param)),
        }))

    def elaborate(self, platform):
        m = Module()

        m.submodules.l0_cfm = l0_cfm = L0ControlFlowMap(self.p)
        m.submodules.rap = rap = ReturnAddressPredictor(8)

        ## The request sent to the FTQ on the previous cycle
        #r_prev_cfr = ControlFlowRequest(self.p).create()

        ## Given the request from the previous cycle, try to predict a 
        ## request for this cycle.
        #m.d.comb += [
        #    l0_cfm.rp.req.valid.eq(r_prev_cfr.valid),
        #    l0_cfm.rp.req.pc.eq(r_prev_cfr.pc),
        #]

        # These wires are used to build an FTQ allocation request
        sel_pc    = Signal(32)
        sel_pred  = Signal(1)
        sel_valid = Signal(1)
        sel_src   = Signal(CFRSource)
        sel_blocks = Signal(self.p.fblk_size_shape)
        sel_passthru = Signal(1)
        resteer_pred = Signal()
        resteer_tgt = Signal(32)

        # We're being resteered to a different block after predecoding.
        with m.If(self.resteer_req.valid):
            with m.Switch(self.resteer_req.op):
                with m.Case(ControlFlowOp.JUMP_DIR):
                    m.d.comb += [
                        resteer_tgt.eq(self.resteer_req.tgt_pc),
                        resteer_pred.eq(0),
                    ]
                with m.Case(ControlFlowOp.CALL_DIR):
                    m.d.comb += [
                        rap.push.req.addr.eq(self.resteer_req.src_pc.bits + 4),
                        rap.push.req.valid.eq(1),
                        resteer_tgt.eq(self.resteer_req.tgt_pc),
                        resteer_pred.eq(0),
                    ]
                with m.Case(ControlFlowOp.RET):
                    m.d.comb += [
                        rap.pop.req.valid.eq(1),
                        resteer_pred.eq(1),
                    ]
                    m.d.comb += [
                        resteer_tgt.eq(rap.head),
                    ]
            m.d.sync += [
                    Print("[CFC] resteer", 
                      Format("pc={:08x}", self.resteer_req.src_pc.bits),
                      Format("tgt={:08x}", resteer_tgt),
                      Format("op={}", self.resteer_req.op),
                      Format("pred={}", resteer_pred),
                ),
            ]

            m.d.comb += [
                sel_pc.eq(resteer_tgt),
                sel_pred.eq(0),
                sel_valid.eq(1),
                sel_passthru.eq(1),
                sel_blocks.eq(4),
                sel_src.eq(CFRSource.RESTEER),
            ]
        # We're receiving a debug request from offcore. 
        with m.Elif(self.dbg.valid):
            m.d.comb += [
                sel_pc.eq(self.dbg.pc),
                sel_pred.eq(0),
                sel_valid.eq(1),
                sel_passthru.eq(1),
                sel_blocks.eq(4),
                sel_src.eq(CFRSource.DEBUG),
            ]
        # We're predicting the previous block
        #with m.Elif(l0_cfm.rp.resp.valid):
        #    m.d.comb += [
        #        sel_pc.eq(l0_cfm.rp.resp.pc),
        #        sel_pred.eq(1),
        #        sel_valid.eq(1),
        #        sel_passthru.eq(1),
        #        sel_blocks.eq(l0_cfm.rp.resp.blocks),
        #        sel_src.eq(CFRSource.PRED0),
        #    ]
        with m.Else():
            m.d.comb += [
                sel_pc.eq(0),
                sel_pred.eq(0),
                sel_valid.eq(0),
                sel_passthru.eq(0),
                sel_blocks.eq(0),
                sel_src.eq(CFRSource.NONE),
            ]


        with m.If(sel_valid):
            m.d.sync += [
                Print(Format("[CFC] select"), 
                      Format("npc={:08x}", sel_pc),
                      Format("blocks={}", sel_blocks),
                      Format("pred={}", sel_pred),
                      Format("src={}", sel_src),
                ),

            ]


        ## Send the selected program counter value to the NFP.
        #m.d.comb += [
        #    nfp.req.pc.eq(sel_pc),
        #    nfp.req.valid.eq(sel_valid),
        #]
        ## Output from the NFP is available on the next cycle
        #m.d.sync += [
        #    r_nfp_pc.eq(nfp.resp.pc),
        #    r_nfp_valid.eq(nfp.resp.valid),
        #]

        ## Capture the selected program counter value from this cycle.
        ## These registers hold information from the previous CFR.
        #r_pc    = Signal(32, init=0x0000_0000)
        #r_pred  = Signal(init=0)
        #r_valid = Signal(init=0)
        #m.d.sync += [
        #    r_pc.eq(sel_pc),
        #    r_pred.eq(sel_pred),
        #    r_valid.eq(sel_valid),
        #]

        # Send a request to the FTQ
        with m.If(self.ftq_sts.ready & sel_valid):
            m.d.sync += [
                self.alloc_req.valid.eq(sel_valid),
                self.alloc_req.vaddr.eq(sel_pc),
                self.alloc_req.passthru.eq(sel_passthru),
                self.alloc_req.blocks.eq(sel_blocks),

                Print(Format("[CFC] Allocate"),
                      Format("vaddr={:08x}", sel_pc),
                )

                #r_prev_cfr.valid.eq(sel_valid),
                #r_prev_cfr.pc.eq(sel_pc),
                #r_prev_cfr.blocks.eq(sel_blocks),
            ]
        with m.Else():
            m.d.sync += [
                self.alloc_req.valid.eq(0),
                self.alloc_req.vaddr.eq(0),
                self.alloc_req.passthru.eq(0),
                self.alloc_req.blocks.eq(0),
            ]

        return m

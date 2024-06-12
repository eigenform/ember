
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth_soc.wishbone import Interface as WishboneInterface

from ember.common import *
from ember.common.queue import *
from ember.param import *
from ember.uarch.fetch import *

from ember.front.fetch import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ftq import *
from ember.front.ifill import *
from ember.front.cfc import *
from ember.front.predecode import *
from ember.front.bpu import *

from ember.dq import *
from ember.decode import *


class EmberFrontend(Component):
    """ Ember frontend. 

    Ports
    =====
    fakeram:
        Interface to instruction memory
    dq_up:
        Upstream interface to the decode queue
    dbg_cf_req:
        Debug input: control-flow request
    dbg_fetch_resp: 
        Debug output: fetch unit response

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "fakeram": Out(FakeRamInterface(param.l1i.line_depth)).array(2),
            "dq_up": Out(CreditQueueUpstream(1, DecodeQueueEntry(param))),
            "dbg_cf_req": In(ControlFlowRequest(param)),
            "dbg_fetch_resp": Out(FetchResponse(param)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        clk_ctr = Signal(8, init=0)
        m.d.sync += clk_ctr.eq(clk_ctr + 1)

        bpu   = m.submodules.bpu   = BranchPredictionUnit(self.p)
        cfc   = m.submodules.cfc   = ControlFlowController(self.p)
        ftq   = m.submodules.ftq   = FetchTargetQueue(self.p)
        ifu   = m.submodules.ifu   = FetchUnit(self.p)
        l1i   = m.submodules.l1i   = L1ICache(self.p)
        itlb  = m.submodules.itlb  = L1ICacheTLB(self.p.l1i)
        ifill = m.submodules.ifill = L1IFillUnit(self.p)
        pfu   = m.submodules.pfu   = L1IPrefetchUnit(self.p)
        pdu   = m.submodules.pdu   = PredecodeUnit(self.p)

        # CFC connections
        connect(m, cfc.alloc_req, ftq.alloc_req)
        connect(m, ftq.sts, cfc.ftq_sts)
        connect(m, flipped(self.dbg_cf_req), cfc.dbg)
        connect(m, bpu.cf_req, cfc.bpu)

        # IFU connections
        connect(m, ifu.l1i_rp, l1i.rp[0])
        connect(m, ifu.tlb_rp, itlb.rp)
        connect(m, ifu.ifill_req, ifill.req[0])
        connect(m, ifu.ifill_sts, ifill.sts)
        connect(m, ifu.pd_req, pdu.req)
        connect(m, ifu.resp, flipped(self.dbg_fetch_resp))

        # IFU connection to the decode queue
        # NOTE: The IFU response changes at clock edges
        dq_entry = Signal(DecodeQueueEntry(self.p))
        dq_credit = Signal(1)
        m.d.comb += [
            dq_entry.data.eq(ifu.result.data),
            dq_entry.ftq_idx.eq(ifu.result.ftq_idx),
            dq_credit.eq(ifu.result.valid),
            self.dq_up.data[0].eq(dq_entry),
            self.dq_up.credit.req.credit.eq(dq_credit),
            self.dq_up.credit.req.valid.eq(dq_credit),
        ]

        # PDU connections
        connect(m, pdu.resp, bpu.pd_resp)

        # PFU connections
        connect(m, pfu.l1i_pp, l1i.pp[0])
        connect(m, pfu.tlb_pp, itlb.pp)
        connect(m, pfu.ifill_req, ifill.req[1])
        connect(m, pfu.ifill_sts, ifill.sts)

        # FTQ connections
        connect(m, ftq.fetch_req, ifu.req)
        connect(m, ftq.fetch_resp, ifu.resp)
        connect(m, ftq.prefetch_req, pfu.req)
        connect(m, ftq.prefetch_resp, pfu.resp)
        connect(m, ftq.ifill_resp[0], ifill.resp[0])
        connect(m, ftq.ifill_resp[1], ifill.resp[1])

        # IFILL connections
        connect(m, ifill.l1i_wp[0], l1i.wp[0])
        connect(m, ifill.l1i_wp[1], l1i.wp[1])
        connect(m, ifill.fakeram[0], flipped(self.fakeram[0]))
        connect(m, ifill.fakeram[1], flipped(self.fakeram[1]))

        return m


class EmberMidCore(Component):
    """ Ember mid-core. 
    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "dq_down": In(CreditQueueDownstream(1, DecodeQueueEntry(param))),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        idu = m.submodules.idu = DecodeUnit(self.p)

        return m


class EmberCore(Component):
    """ Ember core. 

    """

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "fakeram": Out(FakeRamInterface(param.l1i.line_depth)).array(2),
            "dbg_cf_req": In(ControlFlowRequest(param)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        front = m.submodules.front = EmberFrontend(self.p)
        dq = m.submodules.dq = DecodeQueue(self.p)
        midcore = m.submodules.midcore = EmberMidCore(self.p)

        # Connect frontend to memory interface
        connect(m, front.fakeram[0], flipped(self.fakeram[0]))
        connect(m, front.fakeram[1], flipped(self.fakeram[1]))

        # Connect frontend to debug wires
        connect(m, flipped(self.dbg_cf_req), front.dbg_cf_req)

        # Connect decode queue to frontend/midcore
        connect(m, front.dq_up, dq.up)
        connect(m, dq.down, midcore.dq_down)

        return m


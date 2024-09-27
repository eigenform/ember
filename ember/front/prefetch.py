
from amaranth import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth.lib.enum import Enum

from ember.param import *
from ember.common.pipeline import *
from ember.common.lfsr import *
from ember.front.l1i import L1ICacheProbePort, L1IWaySelect
from ember.front.itlb import L1ICacheTLBReadPort
from ember.front.ifill import L1IFillPort, L1IFillStatus, L1IFillSource

from ember.uarch.front import *

class L1IPrefetchUnit(Component):
    """ Instruction prefetch unit. 

    Handles requests (from the FTQ) for prefetching into the L1I cache. 

    This module is basically the same as :class:`FetchUnit`, but there's 
    no cacheline data involved. Instead, we just probe the TLB and tags.

    1. When a probe miss occurs, there are two cases: 

        - A TLB miss occured; we cannot fill the L1I cache until resolving 
          the physical address of the cacheline. 
          Send a request to TLB fill/PTW and report back to the FTQ. 

        - A tag miss occured; the cacheline is not present in the L1I cache.
          Send a request to L1I fill and report back to the FTQ. 

    2. When a probe hit occurs, the data must already be in the L1I cache. 
       This means the prefetch request is ineffective. 
       Report back to the FTQ indicating that the data has been prefetched. 

    This pipeline *must* stall for fill unit availability in the case of 
    a probe miss. 

    Ports
    =====
    req: :class:`PrefetchRequest`
        Prefetch request from the FTQ
    l1i_pp: :class:`L1ICacheProbePort`
        L1I cache probe port
    tlb_pp: :class:`L1ICacheTLBReadPort`
        L1I TLB probe port
    ifill_req: 
        L1I fill request

    """
    def __init__(self, param: EmberParams):
        self.p = param

        self.stage = PipelineStages()
        self.stage.add_stage(1, {
            "vaddr": self.p.vaddr,
            "ftq_idx": self.p.ftq.index_shape,
            "passthru": unsigned(1),
        })
        
        self.r_stall = Signal()

        sig = Signature({
            "sts": Out(PrefetchPipelineStatus()),
            "req": In(PrefetchRequest(param)),
            "resp": Out(PrefetchResponse(param)),
            "l1i_pp": Out(L1ICacheProbePort(param)),
            "tlb_pp": Out(L1ICacheTLBReadPort()),
            "ifill_req": Out(L1IFillPort.Request(param)),
            "ifill_sts": In(L1IFillStatus(param)),
        })
        super().__init__(sig)

    def elaborate_s0(self, m: Module):

        # FIXME: Stall for fill unit availability?
        m.d.comb += [
            self.sts.ready.eq(self.stage[1].ready)
        ]

        # Probe the TLB
        with m.If(self.req.passthru):
            m.d.comb += [
                self.tlb_pp.req.valid.eq(0),
                self.tlb_pp.req.vpn.eq(0),
            ]
        with m.Else():
            m.d.comb += [
                self.tlb_pp.req.valid.eq(self.req.valid),
                self.tlb_pp.req.vpn.eq(self.req.vaddr.sv32.vpn),
            ]

        # Probe all ways in the set
        m.d.comb += [
            self.l1i_pp.req.valid.eq(self.req.valid),
            self.l1i_pp.req.set.eq(self.req.vaddr.l1i.set),
        ]

        # FIXME: Pass to the next stage, otherwise wait
        with m.If(self.stage[1].ready & self.req.valid):
            m.d.sync += [
                self.stage[1].valid.eq(self.req.valid),
                self.stage[1].vaddr.eq(self.req.vaddr),
                self.stage[1].passthru.eq(self.req.passthru),
                self.stage[1].ftq_idx.eq(self.req.ftq_idx),
            ]

    def elaborate_s1(self, m: Module): 
        #m.submodules.lfsr = lfsr = \
        #        EnableInserter(C(1,1))(LFSR(degree=4))
        m.submodules.way_select = way_select = \
                L1IWaySelect(self.p.l1i.num_ways, L1ITag())

        # Drive defaults for FTQ response
        m.d.sync += [
            self.resp.sts.eq(PrefetchResponseStatus.NONE),
            self.resp.vaddr.eq(0),
            self.resp.valid.eq(0),
            self.resp.ftq_idx.eq(0),
        ]

        # Drive defaults for fill unit request
        m.d.sync += [
            self.ifill_req.valid.eq(0),
            self.ifill_req.addr.eq(0),
            self.ifill_req.way.eq(0),
            self.ifill_req.ftq_idx.eq(0),
            self.ifill_req.blocks.eq(0),
            self.ifill_req.src.eq(L1IFillSource.NONE),
        ]

        # The fill unit is available to accept a request
        #m.d.comb += self.stage[1].ready.eq(self.ifill_sts.ready)

        vaddr    = self.stage[1].vaddr
        stage_ok = self.stage[1].valid
        passthru = self.stage[1].passthru
        ftq_idx  = self.stage[1].ftq_idx

        tlb_ok  = (~passthru & self.tlb_pp.resp.valid)
        tlb_hit = self.tlb_pp.resp.hit
        tlb_pte = self.tlb_pp.resp.pte

        tag_tlb  = (tlb_ok & tlb_hit)
        tag_pt   = self.stage[1].passthru
        tag_ok   = (tag_tlb | tag_pt)
        tag_sel  = Mux(tag_pt, vaddr.sv32.vpn, tlb_pte.ppn)
        tag_hit  = way_select.o_hit
        tag_way  = way_select.o_way

        # Way selector inputs
        m.d.comb += [
            way_select.i_valid.eq(tag_ok),
            way_select.i_tag.eq(tag_sel),
        ]
        m.d.comb += [
            way_select.i_tags[way_idx].eq(self.l1i_pp.resp.tag_data[way_idx])
            for way_idx in range(self.p.l1i.num_ways)
        ]

        sts = Signal(PrefetchResponseStatus)
        with m.If(stage_ok & ~tag_ok & ~tlb_hit & ~tag_pt):
            m.d.comb += sts.eq(PrefetchResponseStatus.TLB_MISS)
        with m.Elif(stage_ok & tag_ok & ~tag_hit):
            m.d.comb += sts.eq(PrefetchResponseStatus.L1_MISS)
        with m.Elif(stage_ok & tag_ok & tag_hit):
            m.d.comb += sts.eq(PrefetchResponseStatus.L1_HIT)
        with m.Else():
            m.d.comb += sts.eq(PrefetchResponseStatus.NONE)

        resolved_paddr = Signal(self.p.paddr)
        m.d.comb += [
            resolved_paddr.sv32.ppn.eq(tlb_pte.ppn),
            resolved_paddr.sv32.offset.eq(vaddr.sv32.offset),
        ]

        # Inputs to the L1I fill unit
        paddr_sel = Mux(self.stage[1].passthru, 
            vaddr, 
            resolved_paddr,
        )
        ifill_req_valid = (
            (sts == PrefetchResponseStatus.L1_MISS)
        )

        ifill_fire = Signal()
        ifill_stall = Signal()
        m.d.comb += [
            ifill_fire.eq(ifill_req_valid & self.ifill_sts.ready),
            ifill_stall.eq(ifill_req_valid & ~self.ifill_sts.ready),
        ]

        with m.If(ifill_fire):
            m.d.sync += [
                self.ifill_req.valid.eq(ifill_req_valid),
                self.ifill_req.addr.eq(paddr_sel),
                self.ifill_req.blocks.eq(1),
                #self.ifill_req.way.eq(lfsr.value),
                self.ifill_req.ftq_idx.eq(self.stage[1].ftq_idx),
                self.ifill_req.src.eq(L1IFillSource.PREFETCH),
            ]

        m.d.comb += self.stage[1].ready.eq(~ifill_stall)

        # FIXME: Inputs to TLB fill/PTW would go here..
        m.d.sync += []

        # Respond to the FTQ 
        m.d.sync += [
            self.resp.sts.eq(sts),
            self.resp.vaddr.eq(vaddr),
            self.resp.valid.eq(self.stage[1].valid),
            self.resp.ftq_idx.eq(ftq_idx),
            self.resp.stall.eq(ifill_stall),
        ]

    def elaborate(self, platform):
        m = Module()
        self.elaborate_s0(m)
        self.elaborate_s1(m)
        return m



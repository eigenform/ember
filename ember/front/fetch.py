
from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
from amaranth_soc.wishbone import Signature as WishboneSignature
from amaranth_soc.wishbone import CycleType, BurstTypeExt

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ifill import *
from ember.front.ftq import *
from ember.riscv.paging import *
from ember.sim.fakeram import *

from ember.uarch.fetch import *


class FetchUnit(Component):
    """ Instruction fetch logic. 

    Instruction fetch is responsible for handling requests to bring 
    instruction bytes into the pipeline from the L1I cache.

    There are two cases where a request cannot be completed: 

    1. A miss in the TLB causes the request to stall for the availability of 
       the associated physical address. This causes a PTW request.

    2. A miss in the L1I cache causes the request to stall for the availability
       of the associated cacheline. This causes an L1I fill request.

    Ports
    =====
    req: :class:`FetchRequest`
        Instruction fetch request
    resp: 
        Instruction fetch response
    l1i_rp: :class:`ember.front.l1i.L1ICacheReadPort`
        L1I cache read port
    tlb_rp: :class:`ember.front.itlb.L1ICacheTLBReadPort`
        L1I TLB read port
    ifill_req: :class:`ember.front.ifill.L1IFillRequest`
        L1I fill unit request
    ifill_sts: :class:`ember.front.ifill.L1IFillStatus`
        L1I fill unit status

    """
    def __init__(self, param: EmberParams):
        self.p = param

        self.stage = PipelineStages()
        self.stage.add_stage(1, {
            "vaddr": self.p.vaddr,
            "ftq_idx": FTQIndex(self.p),
            "passthru": unsigned(1),
        })
        self.lfsr = LFSR(degree=4)

        signature = Signature({
            "req": In(FetchRequest(param)),
            "resp": Out(FetchResponse(param)),

            "l1i_rp": Out(L1ICacheReadPort(param)),
            "tlb_rp": Out(L1ICacheTLBReadPort(param.l1i)),

            "ifill_req": Out(L1IFillRequest(param)),
            "ifill_sts": In(L1IFillStatus(param)),
        })
        super().__init__(signature)

    def elaborate_s0(self, m: Module):
        """ Instruction Fetch - Stage #0

        1. Drive inputs to the L1I arrays and to the TLB. 
        2. Results from the L1I arrays and TLB are available on the next cycle. 
        """

        #m.d.sync += Print(Format(
        #    "[ifu_s0] Fetch request for {:08x}", 
        #    self.req.vaddr.bits)
        #)

        # Connect the fetch interface inputs to the TLB read port inputs.
        # Passthrough requests do not use the TLB read port. 
        with m.If(self.req.passthru):
            m.d.comb += [
                self.tlb_rp.req.valid.eq(0),
                self.tlb_rp.req.vpn.eq(0),
            ]
        with m.Else():
            m.d.comb += [
                self.tlb_rp.req.valid.eq(self.req.valid),
                self.tlb_rp.req.vpn.eq(self.req.vaddr.sv32.vpn),
            ]

        # Connect the fetch interface inputs to the cache read port inputs.
        m.d.comb += [
            self.l1i_rp.req.valid.eq(self.req.valid),
            self.l1i_rp.req.set.eq(self.req.vaddr.l1i.set),
        ]

        # Pass the fetch request to stage 1
        m.d.sync += [
            self.stage[1].valid.eq(self.req.valid),
            self.stage[1].vaddr.eq(self.req.vaddr),
            self.stage[1].passthru.eq(self.req.passthru),
            self.stage[1].ftq_idx.eq(self.req.ftq_idx),
        ]

    def elaborate_s1(self, m: Module): 
        """ Instruction Fetch - Stage #1 

        1. If we're handling a passthrough request, output from TLB 
           will be invalid. Instead, we use the VPN to select a matching
           cache way. 

        2. Valid output from the TLB will either indicate a hit or a miss. 
           When a hit occurs, use the PPN to select a matching cache way. 
           When a miss occurs, send a request to the PTW. 

        3. If a matching cache way is found, respond with the hitting line. 
           If no match occurs, send a request to the L1I fill interface. 
           The way index is selected with an LFSR. 

        """

        m.submodules.lfsr = lfsr = EnableInserter(C(1,1))(self.lfsr)
        m.submodules.way_select = way_select = \
                L1IWaySelect(self.p.l1i.num_ways, self.p.l1i.tag_layout)
        l1_line_data = Array(
            self.l1i_rp.resp.line_data[way_idx]
            for way_idx in range(self.p.l1i.num_ways)
        )

        vaddr    = self.stage[1].vaddr
        stage_ok = self.stage[1].valid
        passthru = self.stage[1].passthru
        ftq_idx  = self.stage[1].ftq_idx

        tlb_ok  = (~passthru & self.tlb_rp.resp.valid)
        tlb_hit = self.tlb_rp.resp.hit
        tlb_pte = self.tlb_rp.resp.pte

        tag_tlb  = (tlb_ok & tlb_hit)
        tag_pt   = self.stage[1].passthru
        tag_ok   = (tag_tlb | tag_pt)
        tag_sel  = Mux(tag_pt, vaddr.sv32.vpn, tlb_pte.ppn)
        tag_hit  = way_select.o_hit
        tag_way  = way_select.o_way
        tag_line = Mux(tag_hit, l1_line_data[tag_way], 0)

        # Way selector inputs
        m.d.comb += [
            way_select.i_valid.eq(tag_ok),
            way_select.i_tag.eq(tag_sel),
        ]
        m.d.comb += [
            way_select.i_tags[way_idx].eq(self.l1i_rp.resp.tag_data[way_idx])
            for way_idx in range(self.p.l1i.num_ways)
        ]

        sts = Signal(FetchResponseStatus)
        with m.If(stage_ok & ~tag_ok & ~tlb_hit & ~tag_pt):
            m.d.comb += sts.eq(FetchResponseStatus.TLB_MISS)
        with m.Elif(stage_ok & tag_ok & ~tag_hit):
            m.d.comb += sts.eq(FetchResponseStatus.L1_MISS)
        with m.Elif(stage_ok & tag_ok & tag_hit):
            m.d.comb += sts.eq(FetchResponseStatus.L1_HIT)
        with m.Else():
            m.d.comb += sts.eq(FetchResponseStatus.NONE)

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
        ifill_req_valid = (sts == FetchResponseStatus.L1_MISS)
        m.d.sync += [
            self.ifill_req.valid.eq(ifill_req_valid),
            self.ifill_req.addr.eq(paddr_sel),
            self.ifill_req.way.eq(self.lfsr.value),
        ]

        # FIXME: Inputs to the PTW
        m.d.sync += [
        ]

        m.d.sync += [
            self.resp.sts.eq(sts),
            self.resp.vaddr.eq(vaddr),
            self.resp.valid.eq(self.stage[1].valid),
            self.resp.data.eq(tag_line),
            self.resp.ftq_idx.eq(ftq_idx),
        ]

    def elaborate(self, platform):
        m = Module()
        self.elaborate_s0(m)
        self.elaborate_s1(m)
        return m



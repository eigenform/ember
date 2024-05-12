
from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
from amaranth_soc.wishbone import Signature as WishboneSignature
from amaranth_soc.wishbone import CycleType, BurstTypeExt

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.cache.l1i import *
from ember.cache.itlb import *
from ember.cache.ifill import *
from ember.ftq import *
from ember.riscv.paging import *
from ember.sim.fakeram import *

class FetchRequest(Signature):
    """ A request to fetch a cache line at some virtual address. 

    - ``vaddr``:    Virtual address of the requested cacheline
    - ``passthru``: Bypass virtual-to-physical translation

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready": In(1),
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "passthru": Out(1),
        })

class FetchResponseStatus(Enum):
    NONE   = 0
    L1_HIT = 1
    L1_MISS = 2
    TLB_MISS = 3

class FetchResponse(Signature):
    """ Response to a fetch request.  """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(FetchResponseStatus),
            "data": Out(p.l1i.line_layout),
        })


class FetchUnit(Component):
    """ Instruction fetch logic. 

    Instruction fetch is responsible for handling requests to bring 
    instruction bytes into the pipeline from the L1I cache.

    There are two cases where a request cannot be completed: 

    1. A miss in the TLB causes the request to stall for the availability of 
       the associated physical address. This causes a PTW request.

    2. A miss in the L1I cache causes the request to stall for the availability
       of the associated cacheline. This causes an L1I fill request.

    """
    def __init__(self, param: EmberParams):
        self.p = param

        self.stage = PipelineStages()
        self.stage.add_stage(1, {
            "req_vaddr": self.p.vaddr,
            "passthru": unsigned(1),
        })
        #self.stage.add_stage(2, {
        #    "req_vaddr": unsigned(32),
        #    "passthru": unsigned(1),
        #})
        #self.stage.add_stage(3, {
        #    "req_vaddr": unsigned(32),
        #    "passthru": unsigned(1),
        #})
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

        m.d.sync += Print(Format(
            "[ifu_s0] Fetch request for {:08x}", 
            self.req.vaddr.bits)
        )

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
            self.stage[1].req_vaddr.eq(self.req.vaddr),
            self.stage[1].passthru.eq(self.req.passthru),
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

        req_vaddr = self.stage[1].req_vaddr
        stage_ok = self.stage[1].valid
        passthru = self.stage[1].passthru

        tlb_ok  = (~passthru & self.tlb_rp.resp.valid)
        tlb_hit = self.tlb_rp.resp.hit
        tlb_pte = self.tlb_rp.resp.pte

        tag_tlb  = (tlb_ok & tlb_hit)
        tag_pt   = self.stage[1].passthru
        tag_ok   = (tag_tlb | tag_pt)
        tag_sel  = Mux(tag_pt, req_vaddr.sv32.vpn, tlb_pte.ppn)
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
            resolved_paddr.sv32.offset.eq(req_vaddr.sv32.offset),
        ]

        # Inputs to the L1I fill unit
        paddr_sel = Mux(self.stage[1].passthru, 
            req_vaddr, 
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
            self.resp.vaddr.eq(req_vaddr),
            self.resp.valid.eq(self.stage[1].valid),
            self.resp.data.eq(tag_line),
        ]


        #ifill_valid = ~tgt_hit
        #ifill_ready = self.ifill_sts.ready
        #ifill_ok    = (ifill_valid & ifill_ready)

        #sts = Signal(FetchResponseStatus)
        #l1i_vaddr = View(self.p.l1i.vaddr_layout, self.stage[1].req_vaddr)
        #with m.If(tgt_hit):
        #    m.d.comb += sts.eq(FetchResponseStatus.L1_HIT)
        #with m.Elif(~tgt_hit):
        #    m.d.comb += sts.eq(FetchResponseStatus.L1_MISS)
        #    m.d.comb += [
        #        self.ifill_req.valid.eq(1),
        #        self.ifill_req.set.eq(l1i_vaddr.idx),
        #    ]
        #with m.Elif(tlb_miss):
        #    m.d.comb += sts.eq(FetchResponseStatus.TLB_MISS)
        #with m.Else():
        #    m.d.sync += Assert(1 == 0, 
        #        Format("tgt_hit={} tlb_miss={}", tgt_hit, tlb_miss)
        #    )

        #m.d.sync += [
        #    self.resp.valid.eq(self.stage[1].valid),
        #    self.resp.data.eq(tgt_line),
        #    self.resp.vaddr.eq(self.stage[1].req_vaddr),
        #    self.resp.sts.eq(sts),
        #]




    def elaborate(self, platform):
        m = Module()

        self.elaborate_s0(m)
        self.elaborate_s1(m)

        return m

class FetchUnitHarness(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "fetch_req": In(FetchRequest(param)),
            "fetch_resp": Out(FetchResponse(param)),

            "fakeram": Out(FakeRamInterface()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        ftq   = m.submodules.ftq   = FetchTargetQueue(self.p)
        ifu   = m.submodules.ifu   = FetchUnit(self.p)
        l1i   = m.submodules.l1i   = L1ICache(self.p)
        itlb  = m.submodules.itlb  = L1ICacheTLB(self.p.l1i)
        ifill = m.submodules.ifill = L1IFillUnit(self.p)

        connect(m, ifu.l1i_rp, l1i.rp)
        connect(m, ifu.tlb_rp, itlb.rp)
        connect(m, ifu.req, flipped(self.fetch_req))
        connect(m, ifu.resp, flipped(self.fetch_resp))

        connect(m, ifu.ifill_req, ifill.req)
        connect(m, ifu.ifill_sts, ifill.sts)
        connect(m, ifill.l1i_wp, l1i.wp)
        connect(m, ifill.fakeram, flipped(self.fakeram))


        return m




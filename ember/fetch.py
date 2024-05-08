
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
from ember.riscv.paging import *

class FetchRequest(Signature):
    """ A request to fetch a cache line at some virtual address. """
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready": In(1),
            "valid": Out(1),
            "vaddr": Out(32),
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
            "vaddr": Out(32),
            "sts": Out(FetchResponseStatus),
            "data": Out(p.l1i.line_layout),
        })


class FetchUnit(Component):
    """ Instruction fetch logic. 

    Instruction fetch is responsible for the following: 

    - Providing L1I cache lines to the instruction pipeline
    - Bringing data into the L1I cache from remote memories

    """
    def __init__(self, param: EmberParams):
        self.p = param

        self.stage = PipelineStages()
        self.stage.add_stage(1, {
            "req_vaddr": unsigned(32),
            "passthru": unsigned(1),
        })
        self.stage.add_stage(2, {
            "req_vaddr": unsigned(32),
            "passthru": unsigned(1),
        })
        self.stage.add_stage(3, {
            "req_vaddr": unsigned(32),
            "passthru": unsigned(1),
        })

        signature = Signature({
            "req": In(FetchRequest(param)),
            "resp": Out(FetchResponse(param)),

            "l1i_rp": Out(L1ICacheReadPort(param)),
            "tlb_rp": Out(L1ICacheTLBReadPort(param.l1i)),
        })
        super().__init__(signature)

    def elaborate_s0(self, m: Module):
        """ Instruction Fetch - Stage #0

        Drives inputs to the L1I arrays and to the TLB. 
        Results from the L1I arrays and TLB are available on the next cycle. 
        """

        m.d.sync += Print(Format(
            "[ifu_s0] Fetch request for {:08x}", 
            self.req.vaddr)
        )

        # Connect the fetch interface inputs to the TLB read port inputs.
        # Passthrough requests do not use the TLB read port. 
        tlb_vaddr = View(VirtualAddressSv32(), self.req.vaddr)
        with m.If(self.req.passthru):
            m.d.comb += [
                self.tlb_rp.req.valid.eq(0),
                self.tlb_rp.req.vpn.eq(0),
            ]
        with m.Else():
            m.d.comb += [
                self.tlb_rp.req.valid.eq(self.req.valid),
                self.tlb_rp.req.vpn.eq(tlb_vaddr.vpn),
            ]

        # Connect the fetch interface inputs to the cache read port inputs.
        l1i_vaddr = View(self.p.l1i.vaddr_layout, self.req.vaddr)
        m.d.comb += [
            self.l1i_rp.req.valid.eq(self.req.valid),
            self.l1i_rp.req.set.eq(l1i_vaddr.idx),
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

        """

        tlb_hit  = (self.tlb_rp.resp.valid & self.tlb_rp.resp.hit)
        tlb_miss = (self.tlb_rp.resp.valid & ~self.tlb_rp.resp.hit)
        tlb_pte  = self.tlb_rp.resp.pte

        # Drive all of the tag data to the way selector logic. 
        view = View(VirtualAddressSv32(), self.stage[1].req_vaddr)
        m.submodules.way_select = way_select = \
                L1IWaySelect(self.p.l1i.num_ways, self.p.l1i.tag_layout)
        i_tag = Mux(self.stage[1].passthru, view.vpn, tlb_pte.ppn)
        m.d.comb += [
            way_select.i_tag.eq(i_tag),
            way_select.i_valid.eq(~tlb_miss),
        ]
        m.d.comb += [
            way_select.i_tags[way_idx].eq(self.l1i_rp.resp.tag_data[way_idx])
            for way_idx in range(self.p.l1i.num_ways)
        ]

        tgt_hit = (way_select.o_hit)
        tgt_way = way_select.o_way
        l1_line_data = Array(
            self.l1i_rp.resp.line_data[way_idx]
            for way_idx in range(self.p.l1i.num_ways)
        )
        tgt_line = Mux(tgt_hit, l1_line_data[tgt_way], 0)
        sts = Signal(FetchResponseStatus)
        m.d.sync += [
            self.resp.valid.eq(self.stage[1].valid),
        ]
        with m.If(tgt_hit):
            m.d.sync += [
                self.resp.sts.eq(FetchResponseStatus.L1_HIT),
                self.resp.vaddr.eq(self.stage[1].req_vaddr),
                self.resp.data.eq(tgt_line),
                self.resp.valid.eq(1),
            ]
            m.d.comb += sts.eq(FetchResponseStatus.L1_HIT)
        with m.Elif(~tgt_hit):
            m.d.comb += sts.eq(FetchResponseStatus.L1_MISS)
        with m.Elif(tlb_miss):
            m.d.comb += sts.eq(FetchResponseStatus.TLB_MISS)




    def elaborate(self, platform):
        m = Module()

        self.elaborate_s0(m)
        self.elaborate_s1(m)

        #with m.If(tgt_hit):
        #    m.d.sync += [
        #        Print(Format("[ifu_s1] L1I hit for {:08x} in way {}", 
        #            self.stage[1].req_vaddr, tgt_way)),
        #        self.resp.vaddr.eq(self.stage[1].req_vaddr),
        #        self.resp.data.eq(l1_line_data[tgt_way]),
        #        self.resp.valid.eq(1),
        #    ]
        #with m.Else():
        #    m.d.sync += [
        #        Print(Format("[ifu_s1] L1I miss for {:08x}",
        #            self.stage[1].req_vaddr)),
        #        self.resp.vaddr.eq(self.stage[1].req_vaddr),
        #        self.resp.data.eq(0),
        #        self.resp.valid.eq(1),
        #    ]


        #with m.If(tlb_miss):
        #    m.d.sync += Print("iTLB miss, PTW unimplemented!")
        #    m.d.sync += Assert(~way_select.o_valid,
        #        "Way select output cannot be valid on TLB miss"
        #    )

       
        return m

class FetchUnitHarness(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "fetch_req": In(FetchRequest(param)),
            "fetch_resp": Out(FetchResponse(param)),
        })
        super().__init__(signature)
    def elaborate(self, platform):
        m = Module()

        ifu = m.submodules.ifu = FetchUnit(self.p)
        l1i = m.submodules.l1i = L1ICache(self.p)
        itlb = m.submodules.itlb = L1ICacheTLB(self.p.l1i)

        connect(m, ifu.l1i_rp, l1i.rp)
        connect(m, ifu.tlb_rp, itlb.rp)
        connect(m, ifu.req, flipped(self.fetch_req))
        connect(m, ifu.resp, flipped(self.fetch_resp))

        return m




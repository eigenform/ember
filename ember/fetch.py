
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
            "vaddr": Out(p.xlen),
        })

class FetchResponse(Signature):
    """ Response to a fetch request.  """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": In(1),
            "data": In(p.l1i.line_layout),
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
            "req_vaddr": unsigned(self.p.xlen),
        })
        self.stage.add_stage(2, {
            "req_vaddr": unsigned(self.p.xlen),
        })
        self.stage.add_stage(3, {
            "req_vaddr": unsigned(self.p.xlen),
        })





        signature = Signature({
            # Connection to the ibus for L1I cache fills
            "ibus": Out(WishboneSignature(
                addr_width=30, 
                data_width=32,
                granularity=32,
                features=["err", "cti", "bte"]
            )),

            # Connection to the ibus for TLB fills
            "ibus_tlb": Out(WishboneSignature(
                addr_width=30, 
                data_width=32,
                granularity=32,
                features=["err", "cti", "bte"],
            )),

            "req": In(FetchRequest(param)),
            "resp": Out(FetchResponse(param)),

            # Updates to the 'satp' CSR percolate down into 
            # any MMU logic encompassed by the fetch unit 
            "satp_valid": In(1),
            "satp": In(SatpSv32()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        tlb = m.submodules.tlb = L1ICacheTLB(self.p.l1i)
        l1i = m.submodules.l1i = L1ICache(self.p)

        # =======================================================
        # Keep track of impinging updates to the SATP CSR. 

        satp = Signal(SatpSv32())
        next_satp = Signal(SatpSv32())
        satp_update = Signal()
        m.d.sync += [
            next_satp.eq(self.satp),
            satp_update.eq(self.satp_valid),
        ]

        # =======================================================
        # Wires for the L1 read port response (available at stage 1)
        l1_tag_data = Array(
            Signal(self.p.l1i.tag_layout, name=f"l1_tag_data{idx}") 
            for idx in range(self.p.l1i.num_ways)
        )
        l1_line_data = Array(
            Signal(self.p.l1i.line_layout, name=f"l1_line_data{idx}") 
            for idx in range(self.p.l1i.num_ways)
        )
        l1_data_valid = Signal()
        for way_idx in range(self.p.l1i.num_ways):
            m.d.comb += [
                l1_data_valid.eq(l1i.rp.resp.valid),
                l1_tag_data[way_idx].eq(l1i.rp.resp.tag_data[way_idx]),
                l1_line_data[way_idx].eq(l1i.rp.resp.line_data[way_idx]),
            ]


        # =======================================================
        # Stage 0. 
        # - Drive inputs to the tag/data arrays. 
        # - Drive inputs to the TLB. 
        #
        # NOTE: Do we want to unify the incoming virtual address 
        # into a single layout instead of using two different layouts
        # for the L1I/TLB logic here? 

        # Tell the user if the pipeline is stalled
        m.d.comb += [
            self.req.ready.eq(self.stage[1].ready),
        ]

        # Connect the fetch interface inputs to the TLB read port inputs.
        tlb_vaddr = Signal(VirtualAddressSv32())
        m.d.comb += [
            tlb_vaddr.eq(self.req.vaddr),
            tlb.req.valid.eq(self.req.valid),
            tlb.req.vpn.eq(tlb_vaddr.vpn),
        ]
        # Connect the fetch interface inputs to the cache read port inputs.
        l1i_vaddr = Signal(self.p.l1i.vaddr_layout)
        m.d.comb += [
            l1i_vaddr.eq(self.req.vaddr),
            l1i.rp.req.valid.eq(self.req.valid),
            l1i.rp.req.set.eq(l1i_vaddr.idx),
        ]

        # Pass the fetch request to stage 1
        m.d.sync += [
            self.stage[1].valid.eq(self.req.valid),
            self.stage[1].req_vaddr.eq(self.req.vaddr),
        ]

        # =======================================================
        # Stage 1. 
        # - Read port response from the tag/data arrays is available. 
        # - TLB response is available. 
        #
        # - On TLB miss, start a PTW transaction and stall
        # - On TLB hit, use the PPN to select a matching cache way
        # - On cache miss, start a fill transaction and stall
        # - On cache hit, forward data to fetch response
        
        tlb_hit  = (tlb.resp.valid & self.stage[1].valid)
        tlb_miss = (~tlb.resp.valid & self.stage[1].valid)
        tlb_ppn = tlb.resp.ppn
        with m.If(self.stage[1].valid):
            m.d.sync += Assert(l1_data_valid, "L1 tag/data output invalid?")


        m.d.comb += [
            self.stage[1].ready.eq(tlb_hit),
        ]

        way_match_arr = Array(
            Signal() 
            for way_idx in range(self.p.l1i.num_ways)
        )
        #for way_idx in range(self.p.l1i.num_ways):
        #    m.d.comb += [
        #        way_match[way_idx].eq(
        #            Mux(tlb_hit, (tlb_ppn == l1_tag_data[way_idx]), 0)
        #        ),
        #    ]

        way_match_encoder = PriorityEncoder(exact_log2(self.p.l1i.num_ways))
        way_match_hit  = (~way_match_encoder.n & self.req.valid)
        way_match_idx  = way_match_encoder.o
        way_match_data = Mux(way_match_hit, l1_line_data[way_match_idx], 0)

        m.d.comb += [
            way_match_encoder.i.eq(Cat(*way_match_arr)),
        ]
        




        ## Output to ibus interface
        #fill_adr = Signal(self.p.xlen - 2)
        #m.d.comb += [
        #    self.ibus.adr.eq(fill_adr),
        #    self.ibus.cyc.eq(0),
        #    self.ibus.stb.eq(0),
        #    self.ibus.sel.eq(0),
        #    self.ibus.cti.eq(CycleType.INCR_BURST),
        #    self.ibus.bte.eq(BurstTypeExt.LINEAR),

        #    self.ibus.dat_w.eq(0),
        #    self.ibus.we.eq(0),
        #]

        return m



from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ifill import *
from ember.front.ftq import *
from ember.front.predecode import *
from ember.riscv.paging import *
from ember.sim.fakeram import *

from ember.uarch.front import *


class DemandFetchRequest(Signature):
    """ A request to the demand fetch unit. 

    Members
    =======
    valid:
        This request is valid.
    passthru:
        Bypass virtual-to-physical translation
    vaddr:
        Program counter of the first fetched instruction
    blocks:
        Number of sequential fetch blocks in this request
    ftq_idx:
        FTQ entry index
        
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "passthru": Out(1),
            "vaddr": Out(p.vaddr),
            "blocks": Out(4),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class DemandFetchBlockRequest(StructLayout):
    """ A request for a single fetch block/cacheline passed through 
    the demand fetch pipeline. 

    Members
    =======
    valid:
        This request is valid
    passthru:
        Bypass virtual-to-physical translation
    vaddr:
        Virtual fetch block address associated with this request
    ftq_idx:
        Index of the FTQ entry that generated this request
    blk:
        Position of this block in the parent transaction
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": unsigned(1),
            "passthru": unsigned(1),
            "vaddr": p.vaddr,
            "ftq_idx": p.ftq.index_shape,
            "blk": unsigned(4),
        })


class DemandFetchState(Enum, shape=4):
    """ State associated with the demand fetch unit 

    Members
    =======
    IDLE:
        The demand fetch unit is idle and waiting to start a transaction
    RUN:
        A transaction is occuring. 
    """
    IDLE = 0
    RUN  = 1

class DemandFetchUnit(Component):

    def __init__(self, param: EmberParams):
        self.p = param
        self.stage = PipelineStages()

        # Access stage (L1I Tag/Data access, L1I TLB access)
        self.stage.add_stage(1, {
            "blk_req": DemandFetchBlockRequest(param),
        })

        # Way select stage
        self.stage.add_stage(2, {
            "blk_req": DemandFetchBlockRequest(param),
        })

        signature = Signature({
            "req": In(DemandFetchRequest(param)),
            "resp": Out(FetchResponse(param)),
            "ready": Out(1),

            "l1i_rp": Out(L1ICacheReadPort(param)),
            "tlb_rp": Out(L1ICacheTLBReadPort()),

            "ifill_req": Out(L1IFillPort.Request(param)),
            "ifill_sts": In(L1IFillStatus(param)),

            "pd_req": Out(PredecodeRequest(param)),
            "result": Out(FetchData(param)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()
        self.elaborate_s0(m)
        self.elaborate_s1(m)
        self.elaborate_s2(m)
        return m

    def elaborate_s0(self, m: Module):
        """ Demand Fetch Pipe - Stage 0
        """

        r_next_blk  = Signal(4, init=0)
        r_blocks    = Signal(4)
        r_ftq_idx   = Signal(self.p.ftq.index_shape)
        r_init_addr = Signal(self.p.vaddr)
        r_next_addr = Signal(self.p.vaddr)
        r_state     = Signal(DemandFetchState, init=DemandFetchState.IDLE)
        r_passthru  = Signal()

        with m.Switch(r_state):
            with m.Case(DemandFetchState.IDLE):
                m.d.sync += [
                    self.stage[1].blk_req.valid.eq(0),
                    self.stage[1].blk_req.blk.eq(0),
                    self.stage[1].blk_req.vaddr.eq(0),
                    self.stage[1].blk_req.ftq_idx.eq(0),
                    self.stage[1].blk_req.passthru.eq(0),
                ]

                # Begin a new demand fetch transaction
                with m.If(self.req.valid):
                    m.d.sync += [
                        Print("Start transaction"),
                        Assert(self.req.blocks != 0, 
                            "Demand transaction has no blocks?",
                        ),
                        r_state.eq(DemandFetchState.RUN),
                        r_init_addr.eq(self.req.vaddr),
                        r_next_addr.eq(self.req.vaddr.bits + self.p.l1i.line_bytes),
                        r_ftq_idx.eq(self.req.ftq_idx),
                        r_blocks.eq(self.req.blocks),
                        r_passthru.eq(self.req.passthru),

                        r_next_blk.eq(1),
                        self.stage[1].blk_req.valid.eq(1),
                        self.stage[1].blk_req.blk.eq(1),
                        self.stage[1].blk_req.vaddr.eq(self.req.vaddr),
                        self.stage[1].blk_req.ftq_idx.eq(self.req.ftq_idx),
                        self.stage[1].blk_req.passthru.eq(self.req.passthru),
                    ]

            with m.Case(DemandFetchState.RUN):
                done = (r_next_blk == r_blocks)
                next_addr = (r_next_addr.bits + self.p.l1i.line_bytes)
                next_blk  = r_next_blk + 1
                with m.If(~done):
                    m.d.sync += [
                        r_next_addr.eq(next_addr),
                        r_next_blk.eq(next_blk),
                        self.stage[1].blk_req.valid.eq(1),
                        self.stage[1].blk_req.blk.eq(next_blk),
                        self.stage[1].blk_req.vaddr.eq(next_addr),
                        self.stage[1].blk_req.ftq_idx.eq(r_ftq_idx),
                        self.stage[1].blk_req.passthru.eq(r_passthru),
                    ]
                with m.Else():
                    pass


    def elaborate_s1(self, m: Module):
        """ Demand Fetch Pipe - Stage 1
        """

        req = self.stage[1].blk_req

        m.d.comb += [
            # Connect the TLB read port inputs.
            # Passthrough requests do not use the TLB read port. 
            self.tlb_rp.req.valid.eq(Mux(req.passthru, 0, req.valid)),
            self.tlb_rp.req.vpn.eq(Mux(req.passthru, 0, req.vaddr.sv32.vpn)),

            # Connect the cache read port inputs
            self.l1i_rp.req.valid.eq(req.valid),
            self.l1i_rp.req.set.eq(req.vaddr.l1i.set),
        ]

        # Pass the fetch request to stage 2
        m.d.sync += [
            self.stage[2].blk_req.eq(req)
        ]

    def elaborate_s2(self, m: Module): 
        """ Demand Fetch Pipe - Stage 2
        """

        m.submodules.way_select = way_select = \
                L1IWaySelect(self.p.l1i.num_ways, L1ITag())
        l1_line_data = Array(
            self.l1i_rp.resp.line_data[way_idx]
            for way_idx in range(self.p.l1i.num_ways)
        )

        ifill_ready = self.ifill_sts.ready

        req = self.stage[2].blk_req
        #vaddr    = self.stage[1].vaddr
        #stage_ok = self.stage[1].valid
        #passthru = self.stage[1].passthru
        #ftq_idx  = self.stage[1].ftq_idx

        tlb_ok  = (~req.passthru & self.tlb_rp.resp.valid)
        tlb_hit = self.tlb_rp.resp.hit
        tlb_pte = self.tlb_rp.resp.pte

        tag_tlb  = (tlb_ok & tlb_hit)
        tag_pt   = req.passthru
        tag_ok   = (tag_tlb | tag_pt)
        tag_sel  = Mux(tag_pt, req.vaddr.sv32.vpn, tlb_pte.ppn)
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
        with m.If(req.valid & ~tag_ok & ~tlb_hit & ~tag_pt):
            m.d.comb += sts.eq(FetchResponseStatus.TLB_MISS)
        with m.Elif(req.valid & tag_ok & ~tag_hit):
            m.d.comb += sts.eq(FetchResponseStatus.L1_MISS)
        with m.Elif(req.valid & tag_ok & tag_hit):
            m.d.comb += sts.eq(FetchResponseStatus.L1_HIT)
        with m.Else():
            m.d.comb += sts.eq(FetchResponseStatus.NONE)

        resolved_paddr = Signal(self.p.paddr)
        m.d.comb += [
            resolved_paddr.sv32.ppn.eq(tlb_pte.ppn),
            resolved_paddr.sv32.offset.eq(req.vaddr.sv32.offset),
        ]

        # Inputs to the L1I fill unit
        # 
        # FIXME: Stall this pipe for L1I fill unit availability? 
        paddr_sel = Mux(req.passthru, 
            req.vaddr, 
            resolved_paddr,
        )
        ifill_req_valid = (sts == FetchResponseStatus.L1_MISS)

        # Drive defaults for fill unit request
        m.d.sync += [
            self.ifill_req.valid.eq(0),
            self.ifill_req.addr.eq(0),
            self.ifill_req.way.eq(0),
            self.ifill_req.ftq_idx.eq(0),
            self.ifill_req.src.eq(L1IFillSource.NONE),
        ]

        with m.If(ifill_req_valid & ifill_ready):
            m.d.sync += [
                self.ifill_req.valid.eq(ifill_req_valid),
                self.ifill_req.addr.eq(paddr_sel),
                self.ifill_req.ftq_idx.eq(req.ftq_idx),
                self.ifill_req.src.eq(L1IFillSource.DEMAND),
            ]

        # FIXME: Inputs to the PTW
        m.d.sync += [
        ]

        # Inputs to the predecode unit
        hit_valid = (sts == FetchResponseStatus.L1_HIT)
        m.d.sync += [
            self.pd_req.cline.eq(tag_line),
            self.pd_req.way.eq(tag_way),
            self.pd_req.valid.eq(hit_valid),
            self.pd_req.vaddr.eq(Mux(hit_valid, req.vaddr, 0)),
            self.pd_req.ftq_idx.eq(Mux(hit_valid, req.ftq_idx, 0)),
        ]

        # Output hit data
        m.d.sync += [
            self.result.valid.eq(hit_valid),
            self.result.vaddr.eq(Mux(hit_valid, req.vaddr, 0)),
            self.result.ftq_idx.eq(Mux(hit_valid, req.ftq_idx, 0)),
            self.result.data.eq(tag_line),
        ]
        with m.If(hit_valid):
            cl = Signal(L1ICacheline(self.p))
            m.d.comb += cl.eq(tag_line)
            m.d.sync += Print(Format(
                "L1I Hit {:08x}: {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x}", 
                req.vaddr.bits, cl[0], cl[1], cl[2], cl[3], cl[4], cl[5], cl[6], cl[7],
            ))

        # FTQ response
        m.d.sync += [
            self.resp.sts.eq(sts),
            self.resp.vaddr.eq(req.vaddr),
            self.resp.valid.eq(req.valid),
            self.resp.ftq_idx.eq(req.ftq_idx),
        ]





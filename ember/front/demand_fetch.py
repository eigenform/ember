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
    start_idx: 
        Index of the first valid instruction in this cacheline
    end_idx:
        Index of the last valid instruction in this cacheline
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
            "start_idx": unsigned(p.vaddr.num_off_bits),
            "end_idx": unsigned(p.vaddr.num_off_bits),
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
    STALL:
        A transaction is stalled for the L1I fill unit. 
    """
    IDLE  = 0
    RUN   = 1
    STALL = 2

class DemandFetchUnit(Component):

    def __init__(self, param: EmberParams):
        self.p = param
        self.stage = PipelineStages()

        self.r_state = Signal(DemandFetchState, init=DemandFetchState.IDLE)

        # Indicates when the pipeline is stalled
        self.r_stall  = Signal(init=0)
        # The block number that caused the stall
        self.r_stall_blk = Signal(4)
        # The address that caused the stall
        self.r_stall_vaddr = Signal(self.p.vaddr)

        # The number of cachelines in this transaction.
        self.r_blocks    = Signal(4)

        # The program counter value associated with this transaction 
        # (the address of the first fetched instruction)
        self.r_pc = Signal(self.p.vaddr)
        self.r_init_start_idx = Signal(self.p.vaddr.num_off_bits)
        self.r_last_end_idx   = Signal(self.p.vaddr.num_off_bits)

        # The FTQ index that generated this transaction
        self.r_ftq_idx   = Signal(self.p.ftq.index_shape)
        # Address translation is disabled for this transaction
        self.r_passthru  = Signal()

        # The beat number/block number sent downstream on the previous cycle.
        self.r_blk  = Signal(4, init=0)
        # The address sent downstream on the previous cycle.
        self.r_addr = Signal(self.p.vaddr)

        # Access stage (L1I Tag/Data access, L1I TLB access)
        self.stage.add_stage(1, {
            "blk_req": DemandFetchBlockRequest(param),
            "flush": unsigned(1),
        })

        # Way select stage
        self.stage.add_stage(2, {
            "blk_req": DemandFetchBlockRequest(param),
            "flush": unsigned(1),
        })

        signature = Signature({
            "req": In(DemandFetchRequest(param)),
            "resp": Out(FetchResponse(param)),
            "ready": Out(1),

            "l1i_rp": Out(L1ICacheReadPort(param)),
            "tlb_rp": Out(L1ICacheTLBReadPort()),

            "ifill": Out(L1IFillPort(param)),

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

        m.d.sync += [
            self.stage[1].blk_req.valid.eq(0),
            self.stage[1].blk_req.blk.eq(0),
            self.stage[1].blk_req.vaddr.eq(0),
            self.stage[1].blk_req.ftq_idx.eq(0),
            self.stage[1].blk_req.passthru.eq(0),
        ]

        with m.Switch(self.r_state):
            # When the pipeline is idle, begin a new transaction when we 
            # recieve a valid request. 
            with m.Case(DemandFetchState.IDLE):
                init_off = self.req.vaddr.get_fetch_off()
                init_addr = self.req.vaddr.get_fetch_addr()
                with m.If(self.req.valid):
                    m.d.sync += [
                        Print("Start transaction"),
                        Assert(self.req.blocks != 0, 
                            "Demand transaction has no blocks?",
                        ),
                        # Capture the request
                        self.r_pc.eq(self.req.vaddr),
                        self.r_init_start_idx.eq(init_off),

                        self.r_ftq_idx.eq(self.req.ftq_idx),
                        self.r_blocks.eq(self.req.blocks),
                        self.r_passthru.eq(self.req.passthru),

                        self.r_state.eq(DemandFetchState.RUN),
                        self.ready.eq(0),
                        self.r_addr.eq(init_addr),
                        self.r_blk.eq(1),

                        # Send the first request downstream
                        self.stage[1].blk_req.valid.eq(1),
                        self.stage[1].blk_req.blk.eq(1),
                        self.stage[1].blk_req.vaddr.eq(init_addr),
                        self.stage[1].blk_req.start_idx.eq(init_off),
                        self.stage[1].blk_req.ftq_idx.eq(self.req.ftq_idx),
                        self.stage[1].blk_req.passthru.eq(self.req.passthru),
                    ]

            # When the pipeline is running *and* no stall condition is 
            # occuring, continue sending requests down the pipeline
            with m.Case(DemandFetchState.RUN):
                done      = (self.r_blk == self.r_blocks)
                next_addr = (self.r_addr.bits + self.p.l1i.line_bytes)
                next_blk  = (self.r_blk + 1)
                with m.If(~done & ~self.r_stall & self.stage[1].ready):
                    m.d.sync += [
                        self.r_addr.eq(next_addr),
                        self.r_blk.eq(next_blk),

                        self.stage[1].blk_req.valid.eq(1),
                        self.stage[1].blk_req.blk.eq(next_blk),
                        self.stage[1].blk_req.vaddr.eq(next_addr),
                        self.stage[1].blk_req.ftq_idx.eq(self.r_ftq_idx),
                        self.stage[1].blk_req.passthru.eq(self.r_passthru),
                    ]

            # When the pipeline is stalled, wait for a response from the 
            # fill unit before replaying the transaction [resuming at the
            # block which originally caused the stall]. 
            with m.Case(DemandFetchState.STALL):
                # NOTE: Make sure the stage registers are clear while stalling
                m.d.sync += [
                    self.stage[1].blk_req.eq(0),
                    self.stage[2].blk_req.eq(0),
                ]
                ifill_resp_ok = (
                    (self.ifill.resp.ftq_idx == self.r_ftq_idx) &
                    self.ifill.resp.valid
                )
                with m.If(ifill_resp_ok):
                    m.d.sync += [
                        self.r_state.eq(DemandFetchState.RUN),
                        self.r_stall.eq(0),
                        self.r_addr.eq(self.r_stall_vaddr),
                        self.r_blk.eq(self.r_stall_blk),
                        self.stage[1].blk_req.valid.eq(1),
                        self.stage[1].blk_req.blk.eq(self.r_stall_blk),
                        self.stage[1].blk_req.vaddr.eq(self.r_stall_vaddr),
                        self.stage[1].blk_req.ftq_idx.eq(self.r_ftq_idx),
                        self.stage[1].blk_req.passthru.eq(self.r_passthru),
                    ]


    def elaborate_s1(self, m: Module):
        """ Demand Fetch Pipe - Stage 1
        """

        req = self.stage[1].blk_req

        # Propagate stall signal from second stage to upstream? 
        m.d.comb += self.stage[1].ready.eq(self.stage[2].ready)

        # Drive the TLB and L1I read ports when: 
        #   - The second stage has not resulted in a stall during this cycle
        #   - A stall is not in progress (registered from a previous cycle)
        #   - The input from the previous stage is valid
        with m.If(~self.r_stall & self.stage[2].ready & req.valid):
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

        m.submodules.wsel = wsel = \
                L1IWaySelect(self.p.l1i.num_ways, L1ITag())
        l1_line_data = Array(
            self.l1i_rp.resp.line_data[way_idx]
            for way_idx in range(self.p.l1i.num_ways)
        )

        need_stall = Signal()
        stage2_sts = Signal(FetchResponseStatus)

        ifill_ready = self.ifill_sts.ready
        req = self.stage[2].blk_req
        tlb_hit = self.tlb_rp.resp.hit
        tlb_pte = self.tlb_rp.resp.pte

        # Build the tag used to select a way in the set. 
        # For passthrough requests, interpret the address as physical. 
        # Otherwise, use the result from the TLB. 
        pt_paddr = Signal(self.p.paddr)
        in_tag   = Signal(L1ITag())
        m.d.comb += [
            pt_paddr.eq(req.vaddr.bits),
            in_tag.ppn.eq(Mux(req.passthru, pt_paddr.sv32.ppn, tlb_pte.ppn)),
            in_tag.valid.eq(1),
        ]

        # Obtain the physical address for this access.
        # FIXME: But only if we hit in the TLB!
        resolved_paddr = Signal(self.p.paddr)
        m.d.comb += [
            resolved_paddr.sv32.ppn.eq(tlb_pte.ppn),
            resolved_paddr.sv32.offset.eq(req.vaddr.sv32.offset),
        ]
        paddr_sel = Mux(req.passthru, pt_paddr, resolved_paddr)

        tlb_ok  = (~req.passthru & self.tlb_rp.resp.valid)
        tag_tlb = (tlb_ok & tlb_hit)
        tag_ok  = (tag_tlb | req.passthru)

        # Drive inputs to way select logic
        # FIXME: Don't drive the way select logic when stalled?
        m.d.comb += [
            wsel.i_valid.eq(tag_ok),
            wsel.i_tag.eq(in_tag),
        ]
        m.d.comb += [
            wsel.i_tags[way_idx].eq(self.l1i_rp.resp.tag_data[way_idx])
            for way_idx in range(self.p.l1i.num_ways)
        ]
        tag_line = Mux(wsel.o_hit, l1_line_data[wsel.o_way], 0)

        # Determine the outcome of this access. 
        with m.If(req.valid & ~tag_ok & ~tlb_hit & ~req.passthru):
            m.d.comb += stage2_sts.eq(FetchResponseStatus.TLB_MISS)
            m.d.comb += need_stall.eq(1)
        with m.Elif(req.valid & tag_ok & ~wsel.o_hit):
            m.d.comb += stage2_sts.eq(FetchResponseStatus.L1_MISS)
            m.d.comb += need_stall.eq(1)
        with m.Elif(req.valid & tag_ok & wsel.o_hit):
            m.d.comb += stage2_sts.eq(FetchResponseStatus.L1_HIT)
            m.d.comb += need_stall.eq(0)
        with m.Else():
            m.d.comb += stage2_sts.eq(FetchResponseStatus.NONE)
            m.d.comb += need_stall.eq(0)

        # Propagate stall back to stage 1. 
        # NOTE: Beware, this might happen late in the cycle?
        # There are probably important timing constraints here?
        # Maybe we should do this synchronously? 
        #m.d.comb += self.stage[2].ready.eq(~need_stall)
        m.d.comb += self.stage[2].ready.eq(1)

        # Stall the pipeline on the next cycle.
        # Capture the address and block number so we can replay
        # this transaction after the fill unit responds.
        with m.If(need_stall & ~self.r_stall):
            m.d.sync += [
                self.r_stall.eq(1),
                self.r_state.eq(DemandFetchState.STALL),
                self.r_blk.eq(0),
                self.r_addr.eq(0),
                self.r_stall_blk.eq(req.blk),
                self.r_stall_vaddr.eq(req.vaddr),
                self.stage[1].blk_req.eq(0),
                self.stage[2].blk_req.eq(0),

            ]

        # Send a request to the fill unit. 
        # 
        # NOTE: For now, let's try a fill request for all of the remaining
        # cachelines in this fetch block. 
        #
        # FIXME: This simply uses the physical address without verifying 
        # that the TLB output is valid. 
        m.d.sync += [
            self.ifill.req.valid.eq(0),
            self.ifill.req.addr.eq(0),
            self.ifill.req.way.eq(0),
            self.ifill.req.ftq_idx.eq(0),
            self.ifill.req.src.eq(L1IFillSource.NONE),
        ]
        rem_blks = (self.r_blocks - req.blk + 1)
        ifill_req_valid = (stage2_sts == FetchResponseStatus.L1_MISS)
        with m.If(ifill_req_valid & ifill_ready & ~self.r_stall):
            m.d.sync += [
                self.ifill.req.valid.eq(ifill_req_valid),
                self.ifill.req.addr.eq(paddr_sel),
                self.ifill.req.ftq_idx.eq(self.r_ftq_idx),
                self.ifill.req.blocks.eq(rem_blks),
                self.ifill.req.src.eq(L1IFillSource.DEMAND),
            ]

        # When we hit in the L1I, send the hitting cacheline [and other info]
        # out of the pipeline
        hit_valid = (stage2_sts == FetchResponseStatus.L1_HIT)
        m.d.sync += [
            self.pd_req.cline.eq(0),
            self.pd_req.way.eq(0),
            self.pd_req.valid.eq(0),
            self.pd_req.vaddr.eq(0),
            self.pd_req.ftq_idx.eq(0),

            self.result.valid.eq(0),
            self.result.vaddr.eq(0),
            self.result.ftq_idx.eq(0),
            self.result.data.eq(0),
        ]
        with m.If(hit_valid & ~self.r_stall):
            m.d.sync += [
                self.pd_req.valid.eq(hit_valid),
                self.pd_req.cline.eq(tag_line),
                self.pd_req.way.eq(wsel.o_way),
                self.pd_req.vaddr.eq(Mux(hit_valid, req.vaddr, 0)),
                self.pd_req.ftq_idx.eq(Mux(hit_valid, req.ftq_idx, 0)),

                self.result.valid.eq(hit_valid),
                self.result.vaddr.eq(Mux(hit_valid, req.vaddr, 0)),
                self.result.ftq_idx.eq(Mux(hit_valid, req.ftq_idx, 0)),
                self.result.data.eq(tag_line),
            ]
            cl = Signal(L1ICacheline(self.p))
            m.d.comb += cl.eq(tag_line)
            m.d.sync += Print(Format(
                "L1I Hit {:08x}: {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x} {:08x}", 
                req.vaddr.bits, cl[0], cl[1], cl[2], cl[3], cl[4], cl[5], cl[6], cl[7],
            ))

        # If this is the last block in the transaction, reset the pipeline
        # state (indicating that we're ready for a new transaction).
        last_blk = (req.blk == self.r_blocks)
        complete = (
            (self.r_state == DemandFetchState.RUN) &
            last_blk & ~self.r_stall & ~need_stall
        )
        with m.If(complete):
            m.d.sync += [
                self.r_state.eq(DemandFetchState.IDLE),
                self.r_pc.eq(0),
                self.r_addr.eq(0),
                self.r_ftq_idx.eq(0),
                self.r_blocks.eq(0),
                self.r_passthru.eq(0),
                self.ready.eq(1),
                self.r_blk.eq(0),

                self.stage[1].blk_req.eq(0),
                self.stage[2].blk_req.eq(0),

                # FTQ response
                self.resp.sts.eq(stage2_sts),
                self.resp.vaddr.eq(req.vaddr),
                self.resp.valid.eq(req.valid),
                self.resp.ftq_idx.eq(req.ftq_idx),
            ]



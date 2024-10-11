from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ifill import *
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
    lines:
        Number of sequential cachelines in this request
    ftq_idx:
        FTQ entry index
        
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "passthru": Out(1),
            "vaddr": Out(p.vaddr),
            "lines": Out(p.fblk_size_shape),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class DemandFetchResponse(Signature):
    """ Response to a demand fetch request.

    Members
    =======
    valid: 
        This response is valid
    vaddr:
        Virtual address associated with this response
    sts: :class:`FetchResponseStatus`
        Status associated with this response
    ftq_idx:
        FTQ index responsible for the associated request
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(DemandResponseStatus),
            "resteer": Out(1),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class PredictionSrc(Enum, shape=2):
    """ 
    Members
    =======
    NONE:
        Architectural request
    SEQ:
        Next-sequential prediction
    RAP:
        Return-address prediction
    """
    NONE = 0b00
    SEQ  = 0b01
    RAP  = 0b10

class DemandFetchLineRequest(StructLayout):
    """ A request for an L1I cacheline in the demand fetch pipeline. 

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
    line:
        Position of cacheline block in the parent transaction
    terminal:
        This is the last cacheline in the parent transaction
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "passthru": unsigned(1),
            "vaddr": p.vaddr,
            "start_idx": unsigned(p.vaddr.num_off_bits),
            "end_idx": unsigned(p.vaddr.num_off_bits),
            "ftq_idx": p.ftq.index_shape,
            "line": unsigned(4),
            "mask": unsigned(p.l1i.line_depth),
            "terminal": unsigned(1),
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

    def is_stalled(self) -> Value:
        return (self.r_state == DemandFetchState.STALL)
    def is_running(self) -> Value:
        return (self.r_state == DemandFetchState.RUN)

    def __init__(self, param: EmberParams):
        self.p = param
        self.stage = PipelineStages()

        # The state of the pipeline
        self.r_state = Signal(DemandFetchState, init=DemandFetchState.IDLE)

        # The request in this transaction that caused the current stall
        self.r_stall_req = Signal(DemandFetchLineRequest(self.p))
        self.r_stall_cyc = Signal(8, init=0)

        # The number of cachelines in this transaction.
        self.r_lines    = Signal(self.p.fblk_size_shape)

        # The program counter value associated with this transaction 
        # (the address of the first fetched instruction)
        self.r_pc = Signal(self.p.vaddr)
        self.r_init_start_idx = Signal(self.p.vaddr.num_off_bits)
        self.r_last_end_idx   = Signal(self.p.vaddr.num_off_bits)

        # The FTQ index that generated this transaction
        self.r_ftq_idx   = Signal(self.p.ftq.index_shape)
        # Address translation is disabled for this transaction
        self.r_passthru  = Signal()

        # The beat/line number sent downstream on the previous cycle.
        self.r_blk  = Signal(4, init=0)
        # The address sent downstream on the previous cycle.
        self.r_addr = Signal(self.p.vaddr)

        # Access stage (L1I Tag/Data access, L1I TLB access)
        self.stage.add_stage(1, {
            "req": DemandFetchLineRequest(param),
            "flush": unsigned(1),
        })

        # Way select stage
        self.stage.add_stage(2, {
            "req": DemandFetchLineRequest(param),
            "flush": unsigned(1),
        })

        # Predecode stage
        self.stage.add_stage(3, {
            "req": DemandFetchLineRequest(param),
            "data": L1ICacheline(self.p),
            "flush": unsigned(1),
            "resteer": unsigned(1),
        })

        # Ports
        signature = Signature({
            "req": In(DemandFetchRequest(param)),
            "resp": Out(DemandFetchResponse(param)),
            "ready": Out(1),
            "l1i_rp": Out(L1ICacheReadPort(param)),
            "tlb_rp": Out(L1ICacheTLBReadPort()),
            "ifill": Out(L1IFillPort(param)),
            "ifill_sts": In(L1IFillStatus(param)),
            "result": Out(FetchData(param)),
            "resteer_req": Out(ResteerRequest(self.p)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()
        self.elaborate_s0(m)
        self.elaborate_s1(m)
        self.elaborate_s2(m)
        self.elaborate_s3(m)
        return m

    def elaborate_s0(self, m: Module):
        """ Demand Fetch Pipe - Stage 0

        Control the release of requests for L1I cachelines. 

        .. note::
            We're always trying to predict the next cacheline. 
            By default, the next-sequential cacheline is provided in 
            cases where no single-cycle prediction is available. 

        """

        m.d.sync += [
            self.stage[1].valid.eq(0),
            self.stage[1].req.line.eq(0),
            self.stage[1].req.vaddr.eq(0),
            self.stage[1].req.ftq_idx.eq(0),
            self.stage[1].req.passthru.eq(0),

            self.resp.sts.eq(0),
            self.resp.vaddr.eq(0),
            self.resp.valid.eq(0),
            self.resp.ftq_idx.eq(0),
        ]



        with m.Switch(self.r_state):
            # When the pipeline is idle, begin a new transaction when we 
            # recieve a valid request. 
            with m.Case(DemandFetchState.IDLE):
                init_off = self.req.vaddr.get_fetch_off()
                init_mask = offset2masklut(8, init_off >> 2)
                init_addr = self.req.vaddr.get_fetch_addr()
                with m.If(self.req.valid):
                    m.d.sync += [
                        Print(Format("[DFU] Start transaction"),
                              Format("addr={:08x}", self.req.vaddr.bits),
                        ),
                        Assert(self.req.lines != 0, 
                            "Demand transaction has no lines?",
                        ),
                        # Capture the request
                        self.r_pc.eq(self.req.vaddr),
                        self.r_init_start_idx.eq(init_off),
                        self.r_ftq_idx.eq(self.req.ftq_idx),
                        self.r_lines.eq(self.req.lines),
                        self.r_passthru.eq(self.req.passthru),
                        self.r_addr.eq(init_addr),
                        self.r_blk.eq(1),

                        # Change state
                        self.r_state.eq(DemandFetchState.RUN),
                        self.ready.eq(0),

                        # Send the first request downstream
                        self.stage[1].valid.eq(1),
                        self.stage[1].req.line.eq(1),
                        self.stage[1].req.mask.eq(init_mask),
                        self.stage[1].req.vaddr.eq(init_addr),
                        self.stage[1].req.start_idx.eq(init_off),
                        self.stage[1].req.ftq_idx.eq(self.req.ftq_idx),
                        self.stage[1].req.passthru.eq(self.req.passthru),
                    ]

            # When the pipeline is running *and* no stall condition is 
            # occuring, continue sending requests down the pipeline
            with m.Case(DemandFetchState.RUN):
                done      = (self.r_blk == self.r_lines)
                next_addr = (self.r_addr.bits + self.p.l1i.line_bytes)
                next_blk  = (self.r_blk + 1)
                is_terminal = (next_blk == self.r_lines)
                with m.If(~done & ~self.is_stalled()):
                    m.d.sync += [
                        self.r_addr.eq(next_addr),
                        self.r_blk.eq(next_blk),

                        self.stage[1].valid.eq(1),
                        self.stage[1].req.line.eq(next_blk),
                        self.stage[1].req.vaddr.eq(next_addr),
                        self.stage[1].req.mask.eq(C(0b11111111, 8)),
                        self.stage[1].req.ftq_idx.eq(self.r_ftq_idx),
                        self.stage[1].req.passthru.eq(self.r_passthru),
                        self.stage[1].req.terminal.eq(is_terminal),
                    ]

            # When the pipeline is stalled for L1I fill, wait for a response 
            # from the fill unit before replaying the transaction [resuming at 
            # the block which originally caused the stall]. 
            with m.Case(DemandFetchState.STALL):
                m.d.sync += [
                    self.r_stall_cyc.eq(self.r_stall_cyc + 1),
                    self.stage[1].req.eq(0),
                    self.stage[2].req.eq(0),
                ]
                ifill_resp_ok = (
                    (self.ifill.resp.ftq_idx == self.r_ftq_idx) &
                    self.ifill.resp.valid
                )
                with m.If(ifill_resp_ok):
                    m.d.sync += [
                        #Print(
                        #    Format("[DFU] stage0 addr={:08x}: unstall",
                        #        self.r_stall_req.vaddr.bits
                        #    ),
                        #),
                        self.r_state.eq(DemandFetchState.RUN),
                        self.r_addr.eq(self.r_stall_req.vaddr),
                        self.r_blk.eq(self.r_stall_req.line),
                        self.stage[1].valid.eq(1),
                        self.stage[1].req.eq(self.r_stall_req),
                    ]


    def elaborate_s1(self, m: Module):
        """ Demand Fetch Pipe - Stage 1

        Access the L1I cache and TLB. 
        """
        req = self.stage[1].req
        stage_ok = self.stage[1].valid

        # Drive defaults
        m.d.sync += [
            self.stage[2].valid.eq(0),
            self.stage[2].req.eq(0),
        ]
        m.d.comb += [
            self.tlb_rp.req.valid.eq(0),
            self.tlb_rp.req.vpn.eq(0),
            self.l1i_rp.req.valid.eq(0),
            self.l1i_rp.req.set.eq(0),
        ]

        # Drive the TLB and L1I read ports when: 
        #   - The input from the previous stage is valid
        #   - A stall is not in progress (registered from a previous cycle)
        with m.If(stage_ok & ~self.is_stalled()):
            tlb_req_valid = Mux(req.passthru, 0, stage_ok)
            tlb_req_vpn   = Mux(req.passthru, 0, req.vaddr.sv32.vpn)
            l1i_req_set   = Mux(stage_ok, req.vaddr.l1i.set, 0)
            l1i_req_valid = stage_ok
            m.d.comb += [
                self.tlb_rp.req.valid.eq(tlb_req_valid),
                self.tlb_rp.req.vpn.eq(tlb_req_vpn),
                self.l1i_rp.req.valid.eq(l1i_req_valid),
                self.l1i_rp.req.set.eq(l1i_req_set),
            ]
            m.d.sync += [
                self.stage[2].req.eq(req),
                self.stage[2].valid.eq(1),
                #Print(Format("[DFU] stage1"),
                #      Format("addr={:08x}", req.vaddr.bits),
                #),
            ]

    def elaborate_s2(self, m: Module): 
        """ Demand Fetch Pipe - Stage 2

        Handle hit/miss conditions for the L1I/TLB accesses. 
        """

        m.submodules.wsel = wsel = \
                L1IWaySelect(self.p.l1i.num_ways, L1ITag())
        l1_line_data = Array(
            self.l1i_rp.resp.line_data[way_idx]
            for way_idx in range(self.p.l1i.num_ways)
        )
        req = self.stage[2].req
        stage_ok = self.stage[2].valid

        # Drive defaults
        m.d.sync += [
            self.ifill.req.valid.eq(0),
            self.ifill.req.addr.eq(0),
            self.ifill.req.way.eq(0),
            self.ifill.req.ftq_idx.eq(0),
            self.ifill.req.src.eq(L1IFillSource.NONE),

            self.stage[3].valid.eq(0),
            self.stage[3].data.eq(0),
            self.stage[3].req.eq(0),
            self.result.valid.eq(0),
            self.result.vaddr.eq(0),
            self.result.ftq_idx.eq(0),
            self.result.data.eq(0),
        ]

        need_stall = Signal()
        need_resteer = self.stage[3].resteer
        stage2_sts = Signal(FetchResponseStatus)

        ifill_ready = self.ifill_sts.ready
        tlb_hit = self.tlb_rp.resp.hit
        tlb_pte = self.tlb_rp.resp.pte

        # For passthru requests, treat 'req.vaddr' as a physical address. 
        # Otherwise, use TLB output to build a physical address. 
        passthru_paddr = Signal(self.p.paddr)
        resolved_paddr = Signal(self.p.paddr)
        m.d.comb += [
            passthru_paddr.eq(req.vaddr.bits),
            resolved_paddr.sv32.ppn.eq(tlb_pte.ppn),
            resolved_paddr.sv32.offset.eq(req.vaddr.sv32.offset),
        ]
        paddr_sel = Mux(req.passthru, passthru_paddr, resolved_paddr)

        # Build the tag used to select a way in the set. 
        # For passthrough requests, we use the PPN after "casting" the virtual
        # address as a physical address. Otherwise, we use the TLB output. 
        in_tag = Signal(L1ITag())
        m.d.comb += [
            in_tag.valid.eq(1),
            in_tag.ppn.eq(Mux(req.passthru, 
                passthru_paddr.sv32.ppn, 
                tlb_pte.ppn,
            )),
        ]

        # TLB response is valid and being used
        tlb_ok  = (~req.passthru & self.tlb_rp.resp.valid)
        # An actionable TLB hit is occuring
        tag_tlb = (tlb_ok & tlb_hit)
        # The tag used for way selection is valid
        tag_ok  = (tag_tlb | req.passthru)

        # Drive inputs to way select logic
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
        with m.If(stage_ok & ~tag_ok & ~tlb_hit & ~req.passthru):
            m.d.comb += stage2_sts.eq(FetchResponseStatus.TLB_MISS)
            m.d.comb += need_stall.eq(1)
        with m.Elif(stage_ok & tag_ok & ~wsel.o_hit):
            m.d.comb += stage2_sts.eq(FetchResponseStatus.L1_MISS)
            m.d.comb += need_stall.eq(1)
        with m.Elif(stage_ok & tag_ok & wsel.o_hit):
            m.d.comb += stage2_sts.eq(FetchResponseStatus.L1_HIT)
            m.d.comb += need_stall.eq(0)
        with m.Else():
            m.d.comb += stage2_sts.eq(FetchResponseStatus.NONE)
            m.d.comb += need_stall.eq(0)

        # Stall the pipeline on the next cycle.
        # Capture the address and block number so we can replay
        # this transaction after the fill unit responds.
        with m.If(need_stall & ~self.is_stalled() & ~need_resteer):
            m.d.sync += [
                #Print(
                #    Format("[DFU] stage2 addr={:08x}: stall", req.vaddr.bits),
                #),
                self.r_state.eq(DemandFetchState.STALL),
                self.r_blk.eq(0),
                self.r_addr.eq(0),
                self.r_stall_req.eq(req),
                self.stage[1].req.eq(0),
                self.stage[2].req.eq(0),

            ]

        # Setup a request to the fill unit (valid on the next cycle).
        # 
        # NOTE: This requests all of the remaining cachelines in the block. 
        # NOTE: A resteering event in the predecode stage cancels our request
        # FIXME: This simply uses the physical address without verifying TLB
        #        that the TLB output is valid. 
        rem_blks = (self.r_lines - req.line + 1)
        ifill_req_valid = (stage2_sts == FetchResponseStatus.L1_MISS)
        setup_ifill = (
            ifill_req_valid & ifill_ready & ~self.is_stalled() & ~need_resteer
        )
        with m.If(setup_ifill):
            m.d.sync += [
                self.ifill.req.valid.eq(ifill_req_valid),
                self.ifill.req.addr.eq(paddr_sel),
                self.ifill.req.ftq_idx.eq(self.r_ftq_idx),
                self.ifill.req.blocks.eq(rem_blks),
                self.ifill.req.src.eq(L1IFillSource.DEMAND),
            ]

        # When we hit in the L1I, send the hitting cacheline to the next 
        # stage for predecoding. Do not send data when we are stalled, or
        # when we have cancelled the transaction due to re-steering based on 
        # information from predecode.
        hit_valid = (stage2_sts == FetchResponseStatus.L1_HIT)
        with m.If(hit_valid & ~self.is_stalled() & ~need_resteer):
            m.d.sync += [
                self.stage[3].valid.eq(1),
                self.stage[3].data.eq(tag_line),
                self.stage[3].req.eq(self.stage[2].req),
            ]

    def elaborate_s3(self, m: Module): 
        """ Demand Fetch Pipe - Stage 3

        Predecode an L1I cacheline, potentially resteer the front-end, and
        send the cacheline data out of the pipeline.

        .. note::
            Resteering is an *asynchronous* request to CFC (to produce the
            next FTQ entry that will be ready on the next cycle) and a 
            *synchronous* response to the FTQ indicating that this transaction 
            is terminated. 
            The pipeline is invalidated and ready on the next cycle. 

        .. note::
           Branches cannot produce resteering events in the same way as 
           unconditional control-flow because there is no hinting in the 
           ISA that would allows us to determine whether a branch should be
           treated as "taken" by default. Instead, we only rely on predecode
           to validate the *existence* of branches whose predictions are
           currently pending.

        Resteering *must* occur in the following cases:

        1. The first control-flow instruction is unconditionally-taken and
           the target is known immediately (ie. direct jump/call). 
           If this cacheline is *not* predicted, this is the earliest that we 
           can *architecturally resolve* the address of the next cacheline 
           in the stream.

           If this is *not* the terminal cacheline, this means that the 
           fetch block was misrepresented when this transaction started.

        2. A prediction (ie. linking this cacheline to the cacheline currently
           in the previous stage) was made based on a control-flow instruction
           in this cacheline which (a) does not exist, or (b) does not match
           the predecoder output. This is the earliest that we can detect
           a misprediction. 

        Resteering *may* occur in the following cases:

        1. The first control-flow instruction is indirect and we can guarantee 
           that a high-confidence single-cycle prediction can be made.
           It seems reasonable to allow return-address prediction
           (and correspondingly, let any resteering direct call instructions
           push their return address onto the stack). 

        """
        m.submodules.pdu = pdu = PredecodeUnit(self.p)
        stage_ok = self.stage[3].valid
        req = self.stage[3].req

        # Drive defaults
        m.d.comb += [
            self.resteer_req.valid.eq(0),
            self.resteer_req.src_pc.eq(0),
            self.resteer_req.tgt_pc.eq(0),
            self.resteer_req.op.eq(0),
            self.resteer_req.parent_ftq_idx.eq(0),
            self.resteer_req.parent_line.eq(0),
            self.resteer_req.parent_idx.eq(0),
        ]
        m.d.sync += [
            self.result.valid.eq(0),
            self.result.vaddr.eq(0),
            self.result.ftq_idx.eq(0),
            self.result.mask.eq(0),
            self.result.data.eq(0),
        ]

        # Drive the predecoders
        pd_req = PredecodeRequest(self.p).create()
        pd_resp = PredecodeResponse(self.p).create()
        m.d.comb += [
            pd_req.valid.eq(stage_ok),
            pd_req.mask.eq(req.mask),
            pd_req.cline.eq(Mux(stage_ok, self.stage[3].data, 0)),
            pd_req.vaddr.eq(req.vaddr),
            pd_req.line.eq(req.line),
            pd_req.ftq_idx.eq(req.ftq_idx),
        ]
        connect(m, pd_req, pdu.req)
        connect(m, flipped(pd_resp), pdu.resp)
        info = Array([ pd_resp.info[idx] for idx in range(pdu.width)])

        # Find the first control-flow instruction in the line. 
        has_cf = Signal()
        is_cf = Array([ 
            (info[idx].is_cf & pd_resp.info_valid[idx] & ~info[idx].ill)
            for idx in range(pdu.width)
        ])
        m.submodules.pdenc = pdenc = EmberPriorityEncoder(pdu.width)
        m.d.comb += pdenc.i.eq(Cat(*is_cf))
        m.d.comb += has_cf.eq(Cat(*is_cf).any())

        # Determine if the first control-flow instruction is resteering
        resteer_view = PredecodeInfoView(self.p.vaddr, info[pdenc.o])
        need_resteer = (
            pdenc.valid & 
            resteer_view.resteerable() & 
            ~resteer_view.ill
        )

        # Compute the program counter of the resteering instruction
        resteer_src_pc = Signal(self.p.vaddr)
        m.d.comb += resteer_src_pc.eq(
            Mux(need_resteer, (pd_resp.vaddr.bits + (pdenc.o << 2)), 0)
        )

        # Asynchronously tell the previous stages about resteering
        # FIXME: Is this actually necessary? 
        m.d.comb += self.stage[3].resteer.eq(need_resteer)

        # Create a new mask for the resulting cacheline where the resteering 
        # instruction is the last valid instruction
        resteer_mask = limit2masklut(self.p.l1i.line_depth, pdenc.o)
        result_mask = Mux(need_resteer, resteer_mask, req.mask)

        # *Asynchronously* signal the CFC with a resteering request. 
        with m.If(need_resteer):
            m.d.comb += [
                self.resteer_req.valid.eq(need_resteer),
                self.resteer_req.tgt_pc.eq(resteer_view.tgt),
                self.resteer_req.src_pc.eq(resteer_src_pc),
                self.resteer_req.op.eq(resteer_view.cf_op),
                self.resteer_req.parent_ftq_idx.eq(req.ftq_idx),
                self.resteer_req.parent_line.eq(req.line),
                self.resteer_req.parent_idx.eq(pdenc.o),
            ]

        # Send the resulting cacheline out of the pipeline.
        # NOTE: This *always* occurs when this stage is valid.
        with m.If(stage_ok):
            cl = Signal(L1ICacheline(self.p))
            m.d.comb += cl.eq(self.stage[3].data)
            m.d.sync += Print(
                Format("[DFU] output mask={:08b} addr={:08x}:", 
                       reverse_bits(result_mask),
                       req.vaddr.bits
                ),
                Format("{:08x} {:08x} {:08x} {:08x}",
                       cl[0],cl[1],cl[2],cl[3]
                ),
                Format("{:08x} {:08x} {:08x} {:08x}",
                       cl[4],cl[5],cl[6],cl[7]
                ),
            )
            m.d.sync += [
                self.result.valid.eq(1),
                self.result.vaddr.eq(req.vaddr),
                self.result.ftq_idx.eq(req.ftq_idx),
                self.result.mask.eq(result_mask),
                self.result.data.eq(self.stage[3].data),
            ]

        # Determine if this cacheline completes/terminates the transaction.
        # When this is the last cacheline in the transaction: 
        # - Respond to the FTQ with the appropriate status
        # - Flush the entire pipeline
        complete = (
            stage_ok & self.is_running() & (need_resteer | req.terminal)
        )
        with m.If(complete):
            m.d.sync += [
                self.r_state.eq(DemandFetchState.IDLE),
                self.r_pc.eq(0),
                self.r_addr.eq(0),
                self.r_ftq_idx.eq(0),
                self.r_lines.eq(0),
                self.r_passthru.eq(0),
                self.ready.eq(1),
                self.r_blk.eq(0),
                self.r_stall_cyc.eq(0),

                self.stage[1].valid.eq(0),
                self.stage[1].req.eq(0),
                self.stage[2].valid.eq(0),
                self.stage[2].req.eq(0),
                self.stage[3].valid.eq(0),
                self.stage[3].req.eq(0),

                self.resp.sts.eq(Mux(need_resteer, 
                    DemandResponseStatus.RESTEER,
                    DemandResponseStatus.OK
                )),
                self.resp.vaddr.eq(req.vaddr),
                self.resp.valid.eq(stage_ok),
                self.resp.ftq_idx.eq(req.ftq_idx),
            ]



from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ifill import *
from ember.front.prefetch import *

from ember.uarch.front import *


class FTQAllocRequest(Signature):
    """ A request to allocate an FTQ entry.

    Members
    =======
    valid:
        This request is valid
    vaddr: 
        Program counter value
    passthru:
        Treat this virtual address as a physical address
    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "valid": Out(1),
            "passthru": Out(1),
            "vaddr": Out(param.vaddr),
            "predicted": Out(1),
        })

class FTQFreeRequest(Signature):
    """ A request to free an FTQ entry. 

    Members
    =======
    valid:
        This request is valid
    id:
        Index of the FTQ entry to be freed. 

    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "valid": Out(1),
            "id": Out(param.ftq.index_shape),
        })

class FTQStatusBus(Signature):
    """ Status output from the FTQ.

    Members
    =======
    ready:
        The FTQ is ready to allocate 
    next_ftq_idx:
        The index of the next-allocated FTQ entry

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready": Out(1),
            "next_ftq_idx": Out(p.ftq.index_shape),

        })

class FetchTargetQueue(Component):
    """ Logic for tracking outstanding control-flow requests.

    Each entry in the queue corresponds to a control-flow request used for 
    bringing instruction bytes into the pipeline from the L1I cache. 

    This FTQ is implemented as a circular buffer that maintains pointers to 
    the following entries:

    - The index of the next entry to be sent to the IFU pipe
    - The index of the next entry to be sent to the PFU pipe
    - The index of the next entry to be allocated
    - The index of the next entry to be freed

    Fetch Pointer
    =============

    The fetch pointer indicates the next demand fetch request, which always 
    corresponds to the oldest entry in the queue. 

    - When the entry is ``PENDING``: 

      - Send a request to the IFU and mark as in-flight

    - When the entry is ``FETCH``:

      - Wait for the IFU to respond
      - On a TLB miss, mark as ``XLAT``
      - On an L1I miss, mark as ``FILL``
      - On an L1I hit, increment the fetch pointer and mark as ``COMPLETE``
      - On fill unit or PTW stall, mark as ``STALL``

    - When the entry is ``FILL``:

      - Wait for the fill unit to respond
      - Return to the pending state (and replay)

    - When the entry is ``XLAT``:

      - Wait for the PTW to respond
      - Return to the pending state (and replay)

    - When the entry is ``STALL``: 

      - Wait for either the PTW or fill unit to signal ready
      - Mark as either ``XLAT`` or ``FILL``

    - When the entry is ``COMPLETE``:

      - Wait for the backend to release this entry 
      - Return to the unallocated state


    Ports
    =====

    alloc_req:
        Request to allocate a new FTQ entry.

    free_req:
        Request to free an FTQ entry

    fetch_req:
        Output request to the IFU pipe
    fetch_resp:
        Input response from the IFU pipe

    prefetch_req:
        Output request to the PFU pipe
    prefetch_resp:
        Input response from the PFU pipe

    ifill_resp:
        L1I fill unit responses.

    """

    def __init__(self, param: EmberParams):
        self.p = param
        self.depth = param.ftq.depth
        signature = Signature({

            "sts": Out(FTQStatusBus(param)),

            "alloc_req": In(FTQAllocRequest(param)),

            "free_req": In(FTQFreeRequest(param)),

            "fetch_req": Out(FetchRequest(param)),
            "fetch_resp": In(FetchResponse(param)),

            "prefetch_req": Out(PrefetchRequest(param)),
            "prefetch_resp": In(PrefetchResponse(param)),
            "prefetch_sts": In(PrefetchPipelineStatus()),

            "ifill_resp": In(L1IFillPort.Response(param)).array(2),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()
        #m.d.sync += Print("-----------------------------------------------")

        data_arr = Array(
            Signal(FTQEntry(self.p), name=f"data_arr{idx}") 
            for idx in range(self.depth)
        )

        r_fptr = Signal(self.p.ftq.index_shape, init=0)
        r_pptr = Signal(self.p.ftq.index_shape, init=1)
        r_wptr = Signal(self.p.ftq.index_shape, init=0)
        r_used = Signal(ceil_log2(self.depth+1), init=0)
        r_full = Signal()
        r_pf_credit = Signal(4, init=2)

        # Default assignment for demand request output
        m.d.sync += [
            self.fetch_req.valid.eq(0),
            self.fetch_req.vaddr.eq(0),
            self.fetch_req.passthru.eq(0),

        ]
        # Default assignment for probe request output
        m.d.sync += [
            self.prefetch_req.valid.eq(0),
            self.prefetch_req.vaddr.eq(0),
            self.prefetch_req.passthru.eq(0),
        ]


        # Determine whether or not an allocation can occur this cycle. 
        # Allocate/write a new FTQ entry, incrementing the write pointer.
        next_wptr = r_wptr + 1
        next_used = r_used + 1
        can_alloc = (next_used < self.depth)
        alloc_ok  = (self.alloc_req.valid & can_alloc)
        new_entry = data_arr[r_wptr]
        with m.If(alloc_ok):
            m.d.sync += [
                #Print(Format("Alloc FTQ: idx={}, vaddr={:08x}", r_wptr, self.alloc_req.vaddr.bits)),
                new_entry.vaddr.eq(self.alloc_req.vaddr),
                new_entry.state.eq(FTQEntryState.NONE),
                new_entry.passthru.eq(self.alloc_req.passthru),
                new_entry.predicted.eq(self.alloc_req.predicted),
                new_entry.prefetched.eq(0),
                new_entry.complete.eq(0),
                new_entry.valid.eq(1),
                new_entry.id.eq(r_wptr),
                r_wptr.eq(next_wptr),
                r_used.eq(next_used),
            ]
            # NOTE: If we're allocating into the head of the queue (implying
            # that the queue is empty), immediately setup the demand request
            with m.If(r_wptr == r_fptr):
                m.d.sync += [
                    new_entry.state.eq(FTQEntryState.FETCH),
                    self.fetch_req.valid.eq(1),
                    self.fetch_req.vaddr.eq(self.alloc_req.vaddr),
                    self.fetch_req.passthru.eq(self.alloc_req.passthru),
                    self.fetch_req.ftq_idx.eq(r_wptr),
                ]

        # Determine whether or not the queue will be full [on the next cycle]
        full      = (r_used == self.depth)
        next_full = ((next_used == self.depth) & self.alloc_req.valid)
        m.d.sync += r_full.eq(next_full | full)

        # Drive the FTQ status wires 
        m.d.comb += self.sts.ready.eq(~r_full)
        m.d.comb += self.sts.next_ftq_idx.eq(r_wptr)


        # ----------------------------------------------------------------
        # NOTE: Try to gauge fill unit availability? 
        #

        # Count the number of fill responses generated by prefetch requests.
        # Treat these as received credits that we can use to begin more 
        # prefetch transactions. 
        m.submodules.pf_credit_popcnt = pf_credit_rx = \
                PopCount(len(self.ifill_resp))
        pf_credit_inc = [
            (
                (self.ifill_resp[idx].src == L1IFillSource.PREFETCH) & 
                (self.ifill_resp[idx].valid)
            ) for idx in range(0, len(self.ifill_resp))
        ]
        m.d.comb += [
            pf_credit_rx.i.eq(Cat(*pf_credit_inc)),
        ]



        # ----------------------------------------------------------------
        # Monitor incoming responses from the PFU pipe.
        #
        # NOTE: This effectively performs a random access using the FTQ index 
        # from the response. Seems.. not optimal?
        #
        # Using the FTQ index from the PFU response, and depending on the 
        # response status, move the entry to the appropriate state. 

        pfu_resp = self.prefetch_resp
        with m.If(pfu_resp.valid):
            pfu_resp_tgt = data_arr[pfu_resp.ftq_idx]
            m.d.sync += Assert(pfu_resp_tgt.valid)
            with m.If(~pfu_resp.stall):
                with m.Switch(pfu_resp.sts):
                    with m.Case(FetchResponseStatus.L1_MISS):
                        m.d.sync += [
                            pfu_resp_tgt.state.eq(FTQEntryState.FILL),
                        ]
                    with m.Case(FetchResponseStatus.TLB_MISS):
                        m.d.sync += [
                            pfu_resp_tgt.state.eq(FTQEntryState.XLAT),
                        ]
                    with m.Case(FetchResponseStatus.L1_HIT):
                        m.d.sync += [
                            pfu_resp_tgt.state.eq(FTQEntryState.NONE),
                            pfu_resp_tgt.prefetched.eq(1),
                        ]

        # ----------------------------------------------------------------
        # Monitor incoming responses from the IFU pipe.
        #
        # NOTE: We always expect the FTQ index in the response to match the 
        # current value of 'r_fptr'. 

        ifu_resp   = self.fetch_resp
        with m.If(ifu_resp.valid):
            m.d.sync += Print(Format(
                "Demand Resp: idx={} sts={}",
                ifu_resp.ftq_idx, ifu_resp.sts
            ))
            ifu_resp_tgt = data_arr[r_fptr]
            m.d.sync += Assert(ifu_resp.ftq_idx == r_fptr)
            m.d.sync += Assert(ifu_resp_tgt.valid)
            with m.Switch(ifu_resp.sts):
                with m.Case(FetchResponseStatus.L1_MISS):
                    m.d.sync += [
                        ifu_resp_tgt.state.eq(FTQEntryState.FILL),
                    ]
                with m.Case(FetchResponseStatus.TLB_MISS):
                    m.d.sync += [
                        ifu_resp_tgt.state.eq(FTQEntryState.XLAT),
                    ]
                with m.Case(FetchResponseStatus.L1_HIT):
                    m.d.sync += [
                        ifu_resp_tgt.state.eq(FTQEntryState.NONE),
                        ifu_resp_tgt.complete.eq(1),
                        r_fptr.eq(r_fptr + 1),
                    ]

        # ----------------------------------------------------------------
        # Monitor incoming responses from the L1I fill unit.
        #
        # Using the FTQ index from a fill unit response, set the 'prefetched'
        # bit on the corresponding entry.

        for idx in range(0, len(self.ifill_resp)):
            ifill_resp = self.ifill_resp[idx]
            with m.If(ifill_resp.valid):
                ifill_tgt = data_arr[ifill_resp.ftq_idx]
                m.d.sync += Print(Format(
                    "Fill Response: idx={} port={} src={}",
                    ifill_resp.ftq_idx, idx, self.ifill_resp[idx].src, 
                ))
                with m.Switch(ifill_resp.src):
                    # If the fill request came from a prefetch request, 
                    # mark the entry as prefetched
                    with m.Case(L1IFillSource.PREFETCH):
                        m.d.sync += [ 
                            #Assert(ifill_tgt.state == FTQEntryState.FILL),
                            ifill_tgt.prefetched.eq(1),
                            ifill_tgt.state.eq(FTQEntryState.NONE),
                        ]
                    # If the fill request came from demand fetch, immediately 
                    # replay the request
                    with m.Case(L1IFillSource.DEMAND):
                        m.d.sync += [
                            Assert(ifill_tgt.state == FTQEntryState.FILL),
                            Assert(ifill_tgt.id == r_fptr),
                            ifill_tgt.state.eq(FTQEntryState.FETCH),
                            self.fetch_req.valid.eq(1),
                            self.fetch_req.vaddr.eq(ifill_tgt.vaddr),
                            self.fetch_req.passthru.eq(ifill_tgt.passthru),
                            self.fetch_req.ftq_idx.eq(r_fptr),
                        ]

        # ----------------------------------------------------------------
        # Handle the state of the oldest entry in the queue. 
        #
        # 'r_fptr' always indicates the oldest entry in the queue.
        # This is the current outstanding demand fetch request. 
        #
        # NOTE: The declaration of 'w_ifu_entry' here is an annoying hack
        # (sorry) to give the entry a distinct name when viewing waveforms. 
        # You should be using 'ifu_entry' when you need to drive signals, 
        # and only using 'w_ifu_entry' for sampling them.

        ifu_entry = data_arr[r_fptr]
        w_ifu_entry = Signal(FTQEntry(self.p))
        m.d.comb += [
            w_ifu_entry.eq(ifu_entry)
        ]
        m.d.sync += [
            #Print(Format(
            #    "Demand Fetch: idx={:02}, v={}, addr={:08x}, pref={}, state={}", 
            #    w_ifu_entry.id, w_ifu_entry.valid, w_ifu_entry.vaddr.bits,
            #    w_ifu_entry.prefetched, w_ifu_entry.state,
            #)),
        ]

        with m.If(w_ifu_entry.valid):
            with m.Switch(w_ifu_entry.state):
                # The entry is valid and ready to be sent to the IFU. 
                # Setup a request to the IFU (visible on the next cycle). 
                #
                # NOTE: The IFU pipe is currently non-blocking.
                # If this isn't actually the case, you should be checking some 
                # kind of status here before sending the request. 
                with m.Case(FTQEntryState.NONE):
                    m.d.sync += [
                        Assert(r_fptr == w_ifu_entry.id),
                        ifu_entry.state.eq(FTQEntryState.FETCH),
                        self.fetch_req.valid.eq(1),
                        self.fetch_req.vaddr.eq(w_ifu_entry.vaddr),
                        self.fetch_req.passthru.eq(w_ifu_entry.passthru),
                        self.fetch_req.ftq_idx.eq(r_fptr),
                    ]
                # Otherwise, we're waiting for a response from somewhere else
                with m.Default():
                    pass

        # ----------------------------------------------------------------
        # Select a candidate for prefetch

        # The candidate for prefetch on this cycle
        pfu_entry = data_arr[r_pptr]
        w_pfu_entry = Signal(FTQEntry(self.p))
        m.d.comb += [
            w_pfu_entry.eq(pfu_entry),
        ]


        ## This entry is eligible for prefetch
        #pfu_req_elig = Signal()

        ## A prefetch request is being setup on this cycle. 
        ## The request is visible to the PFU pipe on the subsequent cycle.
        #pfu_req_fire = Signal()

        #m.d.comb += [
        #    pfu_req_elig.eq(
        #        w_pfu_entry.valid & 
        #        ~w_pfu_entry.prefetched & 
        #        (w_pfu_entry.state == FTQEntryState.NONE) & 
        #        (r_pptr != r_fptr) 
        #    ),

        #    pfu_req_fire.eq(
        #        pfu_req_elig & 
        #        self.prefetch_sts.ready &
        #        ~(pfu_resp.valid & pfu_resp.stall)
        #    ),
        #]

        #pf_credit_tx_avail = Signal(2)
        #m.d.comb += [
        #    pf_credit_tx_avail.eq(r_pf_credit + pf_credit_rx.o),
        #]
        #pf_credit_ok = (pf_credit_tx_avail >= 1)
        #pf_credit_tx = Signal(2)
        #pf_credit_next = Mux(pfu_req_fire & pf_credit_ok, 
        #    pf_credit_tx_avail - 1,
        #    pf_credit_tx_avail
        #)
        #m.d.sync += r_pf_credit.eq(pf_credit_next)

        ## Send this entry to the PFU pipe
        #with m.If(pfu_req_fire & pf_credit_ok):
        #    m.d.sync += [
        #        Print(Format("Prefetch Fire: idx={} addr={:08x}", r_pptr, w_pfu_entry.vaddr.bits)),
        #        pfu_entry.state.eq(FTQEntryState.PROBE),
        #        self.prefetch_req.valid.eq(1),
        #        self.prefetch_req.vaddr.eq(w_pfu_entry.vaddr),
        #        self.prefetch_req.passthru.eq(w_pfu_entry.passthru),
        #        self.prefetch_req.ftq_idx.eq(r_pptr),
        #        r_pptr.eq(r_pptr + 1),
        #    ]

        return m


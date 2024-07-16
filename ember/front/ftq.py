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
    """ Logic for tracking outstanding fetch requests. 

    This FTQ is implemented as a circular buffer that maintains pointers to 
    the following entries:

    - The index of the next entry to be sent to the IFU pipe
    - The index of the next entry to be sent to the PFU pipe
    - The index of the next entry to be allocated
    - The index of the next entry to be freed

    Fetch Pointer
    =============

    The fetch pointer tracks the entry at head of the FTQ, which is the 
    next to be fetched and sent to the mid-core for decoding. 

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

            "ifill_resp": In(L1IFillResponse(param)).array(2),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        data_arr = Array(
            Signal(FTQEntry(self.p), name=f"data_arr{idx}") 
            for idx in range(self.depth)
        )

        r_fptr = Signal(self.p.ftq.index_shape, init=0)
        r_pptr = Signal(self.p.ftq.index_shape, init=1)
        r_wptr = Signal(self.p.ftq.index_shape, init=0)
        r_used = Signal(ceil_log2(self.depth+1), init=0)
        r_full = Signal()

        next_wptr = r_wptr + 1
        next_used = r_used + 1
        can_alloc = (next_used <= self.depth)
        alloc_ok  = (self.alloc_req.valid & can_alloc)

        full      = (r_used == self.depth)
        next_full = ((next_used == self.depth) & self.alloc_req.valid)
        m.d.sync += r_full.eq(next_full | full)

        m.d.comb += self.sts.ready.eq(~r_full)
        m.d.comb += self.sts.next_ftq_idx.eq(r_wptr)

        # Allocate new FTQ entries and increment the write pointer
        new_entry = data_arr[r_wptr]
        with m.If(alloc_ok):
            m.d.sync += [
                new_entry.vaddr.eq(self.alloc_req.vaddr),
                new_entry.state.eq(FTQEntryState.PENDING),
                new_entry.passthru.eq(self.alloc_req.passthru),
                new_entry.predicted.eq(self.alloc_req.predicted),
                r_wptr.eq(next_wptr),
                r_used.eq(next_used),
            ]

        # ----------------------------------------------------------------

        # Translate incoming IFU response to the next FTQ entry state. 
        ifu_resp = self.fetch_resp
        ifu_resp_state = Signal(FTQEntryState)
        ifu_resp_hit = (
            ifu_resp.valid & (ifu_resp.sts == FetchResponseStatus.L1_HIT)
        )
        with m.Switch(ifu_resp.sts):
            with m.Case(FetchResponseStatus.NONE):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.NONE)
            with m.Case(FetchResponseStatus.L1_MISS):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.FILL)
            with m.Case(FetchResponseStatus.TLB_MISS):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.XLAT)
            with m.Case(FetchResponseStatus.L1_HIT):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.COMPLETE)

        # Default assignment for IFU request output
        m.d.sync += [
            self.fetch_req.valid.eq(0),
            self.fetch_req.vaddr.eq(0),
            self.fetch_req.passthru.eq(0),

        ]

        # Translate incoming PFU probe response to the next FTQ entry state. 
        pfu_resp = self.prefetch_resp
        pfu_resp_state = Signal(FTQEntryState)
        pfu_resp_hit = (
            pfu_resp.valid & (ifu_resp.sts == FetchResponseStatus.L1_HIT)
        )
        with m.Switch(pfu_resp.sts):
            with m.Case(FetchResponseStatus.NONE):
                m.d.comb += pfu_resp_state.eq(FTQEntryState.NONE)
            with m.Case(FetchResponseStatus.L1_MISS):
                m.d.comb += pfu_resp_state.eq(FTQEntryState.FILL)
            with m.Case(FetchResponseStatus.TLB_MISS):
                m.d.comb += pfu_resp_state.eq(FTQEntryState.XLAT)
            with m.Case(FetchResponseStatus.L1_HIT):
                m.d.comb += pfu_resp_state.eq(FTQEntryState.PENDING)

        # Default assignment for PFU request output
        m.d.sync += [
            self.prefetch_req.valid.eq(0),
            self.prefetch_req.vaddr.eq(0),
            self.prefetch_req.passthru.eq(0),
        ]

        # ----------------------------------------------------------------

        # Pointer to the current entry moving through the IFU
        ifu_entry = data_arr[r_fptr]

        # Handle the current FTQ entry being fetched. 
        with m.Switch(ifu_entry.state):
            with m.Case(FTQEntryState.NONE): 
                #m.d.sync += Print("No IFU entry this cycle?")
                pass

            # This entry is waiting to be sent to the IFU. 
            # Setup to send on the next cycle. 
            with m.Case(FTQEntryState.PENDING):
                m.d.sync += [
                    ifu_entry.state.eq(FTQEntryState.FETCH),
                    self.fetch_req.valid.eq(1),
                    self.fetch_req.vaddr.eq(ifu_entry.vaddr),
                    self.fetch_req.passthru.eq(ifu_entry.passthru),
                    self.fetch_req.ftq_idx.eq(r_fptr),
                ]

            # Entry is moving through the IFU pipe.
            #
            # When the IFU responds with a hit, increment the pointer.
            # Otherwise, when the IFU responds with a miss, move to the 
            # appropriate state. 
            #
            # Currently, the IFU is responsible for sending a signal to the
            # PTW or fill unit on a miss (otherwise, the logic would be here).
            with m.Case(FTQEntryState.FETCH):
                with m.If(ifu_resp.valid):
                    m.d.sync += [
                        #Assert(r_fptr == ifu_resp.ftq_idx),
                        ifu_entry.state.eq(ifu_resp_state),
                    ]
                with m.If(ifu_resp_hit):
                    m.d.sync += r_fptr.eq(r_fptr + 1)

            # Entry is moving through the fill unit. 
            # When a matching response is received from the fill unit, 
            # replay the IFU request on the next cycle. 
            with m.Case(FTQEntryState.FILL):
                ifill_match0 = (self.ifill_resp[0].ftq_idx == r_fptr)
                ifill_match1 = (self.ifill_resp[1].ftq_idx == r_fptr)
                resp_ok0 = (ifill_match0 & self.ifill_resp[0].valid)
                resp_ok1 = (ifill_match1 & self.ifill_resp[1].valid)
                with m.If(resp_ok0 | resp_ok1):
                    m.d.sync += [
                        #ifu_entry.state.eq(FTQEntryState.PENDING),
                        ifu_entry.state.eq(FTQEntryState.FETCH),
                        self.fetch_req.valid.eq(1),
                        self.fetch_req.vaddr.eq(ifu_entry.vaddr),
                        self.fetch_req.passthru.eq(ifu_entry.passthru),
                        self.fetch_req.ftq_idx.eq(r_fptr),
                    ]

        # ----------------------------------------------------------------

        pfu_entry = data_arr[r_pptr]
        with m.Switch(pfu_entry.state):
            with m.Case(FTQEntryState.NONE): pass
            with m.Case(FTQEntryState.PENDING):
                with m.If(self.prefetch_sts.ready):
                    m.d.sync += [
                        pfu_entry.state.eq(FTQEntryState.PREFETCH),
                        self.prefetch_req.valid.eq(1),
                        self.prefetch_req.vaddr.eq(pfu_entry.vaddr),
                        self.prefetch_req.passthru.eq(pfu_entry.passthru),
                        self.prefetch_req.ftq_idx.eq(r_pptr),
                        r_pptr.eq(r_pptr + 1),
                    ]




#        # ----------------------------------------------------------------
#        # Pointer to the current entry moving through the PFU
#        pfu_entry = data_arr[r_pptr]
#
#        # Handle the current FTQ entry being prefetched
#        with m.Switch(pfu_entry.state):
#            with m.Case(FTQEntryState.NONE):
#                #m.d.sync += Print("No PFU entry this cycle?")
#                pass
#
#            # The entry is waiting to begin prefetch. 
#            # Start the prefetch request on the next cycle. 
#            with m.Case(FTQEntryState.PENDING):
#                m.d.sync += [ 
#                    #Assert(pfu_entry.prefetched == 0, "already prefetched?"),
#                    pfu_entry.state.eq(FTQEntryState.PREFETCH),
#                    self.prefetch_req.valid.eq(1),
#                    self.prefetch_req.vaddr.eq(pfu_entry.vaddr),
#                    self.prefetch_req.passthru.eq(pfu_entry.passthru),
#                    self.prefetch_req.ftq_idx.eq(r_pptr),
#                ]
#
#            # Entry is moving through the PFU pipe. 
#            #
#            # When the PFU probe responds with a hit in the L1I, mark the 
#            # entry as prefetched and increment the pointer. 
#            #
#            # Otherwise, if the PFU probe results in a miss, move to the 
#            # appropriate state on the next cycle.
#            with m.Case(FTQEntryState.PREFETCH): 
#                with m.If(pfu_resp.valid):
#                    m.d.sync += [
#                        #Assert(r_pptr == pfu_resp.ftq_idx),
#                        pfu_entry.state.eq(pfu_resp_state),
#                    ]
#                with m.If(pfu_resp_hit):
#                    m.d.sync += r_pptr.eq(r_pptr + 1)
#                    m.d.sync += pfu_entry.prefetched.eq(1)
#
#            # Entry is moving through the fill unit. 
#            #
#            # When a matching response is received from the fill unit, 
#            # mark the entry as prefetched and increment the pointer. 
#            with m.Case(FTQEntryState.FILL):
#                ifill_match0 = (self.ifill_resp[0].ftq_idx == r_pptr)
#                ifill_match1 = (self.ifill_resp[1].ftq_idx == r_pptr)
#                resp_ok0 = (ifill_match0 & self.ifill_resp[0].valid)
#                resp_ok1 = (ifill_match1 & self.ifill_resp[1].valid)
#                with m.If(resp_ok0 | resp_ok1):
#                    m.d.sync += pfu_entry.state.eq(FTQEntryState.PENDING)
#                    m.d.sync += pfu_entry.prefetched.eq(1)
#                    m.d.sync += r_pptr.eq(r_pptr + 1)

        return m


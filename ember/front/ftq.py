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

from ember.uarch.fetch import *

class FTQEntryState(Enum, shape=3):
    """ State of an FTQ entry.

    Values
    ======
    NONE:
        FTQ entry is empty
    PENDING:
        Request is eligible for service by the IFU
    FETCH:
        Request is moving through the IFU
    FILL:
        Request stalled for L1I miss
    XLAT:
        Request stalled for TLB miss
    COMPLETE:
        Request completed

    """
    NONE     = 0
    PENDING  = 1
    FETCH    = 2
    FILL     = 3
    XLAT     = 4
    COMPLETE = 5

class FTQEntry(StructLayout):
    """ Layout of an entry in the Fetch Target Queue. 
    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "vaddr": param.vaddr,
            #"src": FTQEntrySource,
            "state": FTQEntryState,
            "passthru": unsigned(1),
            "id": FTQIndex(param),
        })

class FTQAllocRequest(Signature):
    """ A request to allocate an FTQ entry.

    - ``vaddr``: Virtual address of the requested cacheline
    - ``src``: The event that generated this request
    - ``passthru``: Treat this virtual address as a physical address

    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "valid": Out(1),
            "passthru": Out(1),
            "vaddr": Out(param.vaddr),
            #"src": Out(FTQEntrySource),
        })

class FTQFreeRequest(Signature):
    """ A request to free an FTQ entry. """
    def __init__(self, param: EmberParams):
        super().__init__({
            "valid": Out(1),
            "id": Out(FTQIndex(param)),
        })



class FetchTargetQueue(Component):
    """ Logic for tracking outstanding fetch requests. 

    1. Emit a request to the fetch unit 
    2. Fetch unit responds with some status
    3. Entries associated with L1I/TLB misses are parked until signals
       from the L1I fill unit or PTW cause them to replay

    Rationale & Notes
    =================
    - FTQ entries are MSHRs for the L1I, makes IFU non-blocking
    - Decouples branch retire from the IFU
    - Decouples branch prediction from the IFU
    - Opportunistic prefetch for pending requests that are expected to miss
    - Opportunistic prefetch for predicted branch targets (!!)

    Ports
    =====
    alloc_req:
        Request to allocate a new FTQ entry
    free_req:
        Request to free an FTQ entry
    fetch_req:
        Instruction fetch request
    fetch_resp:
        Instruction fetch response
    ifill_resp:
        L1I fill unit response

    """

    def __init__(self, param: EmberParams):
        self.p = param
        self.depth = param.fetch.ftq_depth
        signature = Signature({
            "alloc_req": In(FTQAllocRequest(param)),
            "free_req": In(FTQFreeRequest(param)),

            "fetch_req": Out(FetchRequest(param)),
            "fetch_resp": In(FetchResponse(param)),

            "ifill_resp": In(L1IFillResponse(param)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        data_arr = Array(
            Signal(FTQEntry(self.p), name=f"data_arr{idx}") 
            for idx in range(self.depth)
        )

        r_fptr = Signal(FTQIndex(self.p), init=0)
        r_wptr = Signal(FTQIndex(self.p), init=0)
        r_used = Signal(ceil_log2(self.depth+1), init=0)
        full = (r_used == self.depth)

        # Allocate a new FTQ entry
        alloc_ok = (self.alloc_req.valid & ~full)
        with m.If(alloc_ok):
            m.d.sync += [
                data_arr[r_wptr].vaddr.eq(self.alloc_req.vaddr),
                data_arr[r_wptr].state.eq(FTQEntryState.PENDING),
                data_arr[r_wptr].passthru.eq(self.alloc_req.passthru),
                r_used.eq(r_used + 1),
                r_wptr.eq(r_wptr + 1),
            ]

        # Compute the index of the entry sent to the IFU on the next cycle.
        #
        # FIXME: This is placeholder logic and is not correct: we're just 
        # picking the pending entry with the lowest index in the FTQ 
        m.submodules.pending_encoder = pending_encoder = \
                PriorityEncoder(self.depth)
        next_fptr = Signal(FTQIndex(self.p))
        next_fptr_valid = Signal()
        pending_arr = Array( 
            Signal(name=f"pending_arr{idx}") for idx in range(self.depth)
        )
        m.d.comb += [
            pending_arr[idx].eq(data_arr[idx].state == FTQEntryState.PENDING)
            for idx in range(self.depth)
        ]
        m.d.comb += [
            pending_encoder.i.eq(Cat(*pending_arr)),
            next_fptr.eq(pending_encoder.o),
            next_fptr_valid.eq(~pending_encoder.n),
        ]
        with m.If(next_fptr_valid):
            m.d.sync += r_fptr.eq(next_fptr)


        # On the next cycle, promote an FTQ entry to the 'FETCH' state and 
        # send a request to the IFU on the next cycle. 
        ifu_entry = data_arr[r_fptr]
        with m.If(ifu_entry.state == FTQEntryState.PENDING):
            m.d.sync += [
                self.fetch_req.valid.eq(1),
                self.fetch_req.vaddr.eq(ifu_entry.vaddr),
                self.fetch_req.passthru.eq(ifu_entry.passthru),
                data_arr[r_fptr].state.eq(FTQEntryState.FETCH),
            ]
        with m.Else():
            m.d.sync += [
                self.fetch_req.valid.eq(0),
                self.fetch_req.vaddr.eq(0),
                self.fetch_req.passthru.eq(0),
            ]

        # The IFU response determines the next state of the associated entry.
        # Translate the IFU response to FTQ entry state. 
        ifu_resp = self.fetch_resp
        ifu_resp_state = Signal(FTQEntryState)
        with m.Switch(ifu_resp.sts):
            with m.Case(FetchResponseStatus.NONE):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.NONE)
            with m.Case(FetchResponseStatus.L1_MISS):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.FILL)
            with m.Case(FetchResponseStatus.TLB_MISS):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.XLAT)
            with m.Case(FetchResponseStatus.L1_HIT):
                m.d.comb += ifu_resp_state.eq(FTQEntryState.COMPLETE)
        
        ifu_resp_complete = (
            ifu_resp.valid & (ifu_resp.sts == FetchResponseStatus.L1_HIT)
        )

        # When the IFU responds, change the state of the entry accordingly
        #
        # FIXME: Why are there unreachable cases? 
        with m.If(ifu_resp.valid):
            m.d.sync += [
                data_arr[ifu_resp.ftq_idx].state.eq(ifu_resp_state),
            ]
            with m.Switch(ifu_resp_state):
                with m.Case(FTQEntryState.FILL): pass
                with m.Case(FTQEntryState.XLAT): pass
                with m.Case(FTQEntryState.COMPLETE): pass
                with m.Default():
                    m.d.sync += [
                        Print(Format(
                            "Unreachable FTQ state {} for IFU response",
                            ifu_resp_state
                        )),
                        Assert(1 == 0),
                    ]

        # When the L1I fill unit responds, promote the corresponding entry 
        # to the pending state
        with m.If(self.ifill_resp.valid):
            m.d.sync += [
                data_arr[self.ifill_resp.ftq_idx].state.eq(FTQEntryState.PENDING),
            ]


        return m



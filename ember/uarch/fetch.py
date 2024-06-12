
from amaranth import *
from amaranth.utils import ceil_log2, exact_log2
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.param import *

class FTQIndex(Shape):
    """ An index into the FTQ. """
    def __init__(self, param: EmberParams):
        super().__init__(width=exact_log2(param.fetch.ftq_depth))

class FTQEntryState(Enum, shape=4):
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
    PREFETCH = 2
    FETCH    = 3
    FILL     = 4
    XLAT     = 5
    COMPLETE = 6

class FTQEntry(StructLayout):
    """ Layout of an entry in the Fetch Target Queue. 

    Members
    =======
    vaddr:
        Program counter value associated with this entry
    state:
        State associated with this entry
    prefetched:
        Indicates when an entry has been prefetched into the L1I cache
    passthru:
        Indicates when the program counter value is a physical address
    id: 
        Identifier for this entry

    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "vaddr": param.vaddr,
            "state": FTQEntryState,
            "prefetched": unsigned(1),
            "predicted": unsigned(1),
            "passthru": unsigned(1),
            "id": FTQIndex(param),
        })



class DecodeQueueEntry(StructLayout):
    """ Layout of an entry in the decode queue. 

    Members
    =======
    data:
        L1I cacheline data
    ftq_idx:
        FTQ index associated with this entry
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "data": p.l1i.line_layout,
            "ftq_idx": FTQIndex(p),
        })


class FetchResponseStatus(Enum, shape=2):
    """ Status of a fetch request that has passed through the IFU. 

    Values
    ======
    NONE:
    L1_HIT:
        Request hit in the L1 instruction cache
    L1_MISS:
        Request missed in the L1 instruction cache
    TLB_MISS:
        Request missed in the L1I TLB

    """
    NONE     = 0
    L1_HIT   = 1
    L1_MISS  = 2
    TLB_MISS = 3

class FetchRequest(Signature):
    """ A request to fetch a cache line at some virtual address. 

    Members
    =======
    vaddr:
        Virtual address of the requested cacheline
    passthru: 
        Bypass virtual-to-physical translation

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready": In(1),
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "passthru": Out(1),
            "ftq_idx": Out(FTQIndex(p)),
        })

class FetchResponse(Signature):
    """ Response to a fetch request.

    Members
    =======
    valid: 
        This response is valid
    vaddr:
        Virtual address associated with this response
    sts: :class:`FetchResponseStatus`
        Status associated with this response
    data:
        Response data (an L1I cache line)
    ftq_idx:
        FTQ index responsible for the associated request

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(FetchResponseStatus),
            "ftq_idx": Out(FTQIndex(p)),
        })

class FetchData(Signature):
    """ Response data associated with an instruction fetch request. 

    Members
    =======
    valid:
        This data is valid
    vaddr:
        Program counter value used to fetch this data
    ftq_idx:
        Index of the associated FTQ entry
    data:
        L1I cacheline data

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "ftq_idx": Out(FTQIndex(p)),
            "data": Out(p.l1i.line_layout),
        })


class PrefetchResponseStatus(Enum, shape=2):
    """ Status for a prefetch request. 

    Values
    ======
    NONE:
    L1_HIT:
        Request hit in the L1 instruction cache
    L1_MISS:
        Request missed in the L1 instruction cache
    TLB_MISS:
        Request missed in the L1I TLB
    """
    NONE     = 0
    L1_HIT   = 1
    L1_MISS  = 2
    TLB_MISS = 3

class PrefetchRequest(Signature):
    """ A request to prefetch a cacheline into the L1I cache. 

    Members
    =======
    valid:
        This request is valid
    passthru:
        Treat this virtual address as a physical address.
    ftq_idx:
        The FTQ index responsible for this request.
    vaddr:
        The virtual address of the requested cacheline. 

    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "valid": Out(1),
            "passthru": Out(1),
            "ftq_idx": Out(FTQIndex(param)),
            "vaddr": Out(param.vaddr),
        })

class PrefetchResponse(Signature):
    """ Response to a prefetch request.

    Members
    =======
    valid: 
        This response is valid
    vaddr:
        Virtual address associated with this response
    sts: :class:`PrefetchResponseStatus`
        Status associated with this response
    ftq_idx:
        FTQ index responsible for the associated request

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(FetchResponseStatus),
            "ftq_idx": Out(FTQIndex(p)),
        })



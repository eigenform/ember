from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory

from ember.common import *
from ember.common.pipeline import *
from ember.param import *
from ember.cache.l1i import *
from ember.cache.itlb import *
from ember.cache.ifill import *

class FTQEntryState(Enum):
    NONE = 0
    # Fetch request is stalled for L1I fill
    FILL_STALL = 1
    # Fetch request is stalled for TLB fill
    XLAT_STALL = 2
    # Fetch request completed
    COMPLETE   = 3

class FTQEntrySource(Enum):
    NONE     = 0
    # Fetch request from retired control flow event
    REDIRECT  = 1

class FTQIndex(Shape):
    """ An index into the FTQ. """
    def __init__(self, param: EmberParams):
        super().__init__(width=exact_log2(param.fetch.ftq_depth))

class FTQEntry(StructLayout):
    """ Layout of an entry in the Fetch Target Queue. 
    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "vaddr": param.vaddr,
            "src": FTQEntrySource,
            "state": FTQEntryState,

        })

class FTQAllocRequest(Signature):
    """ A request to allocate an FTQ entry. """
    def __init__(self, param: EmberParams):
        super().__init__({
            "vaddr": param.vaddr,
            "src": FTQEntrySource,
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

    """

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        data_arr = Array(
            Signal(FTQEntry(self.p)) for _ in range(self.p.fetch.ftq_depth)
        )
        valid_arr = Array(
            Signal() for _ in range(self.p.fetch.ftq_depth)
        )

        return m



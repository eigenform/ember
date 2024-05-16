
from amaranth import *
from amaranth.utils import ceil_log2, exact_log2
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.param import *

class FTQIndex(Shape):
    """ An index into the FTQ. """
    def __init__(self, param: EmberParams):
        super().__init__(width=exact_log2(param.fetch.ftq_depth))


class FetchResponseStatus(Enum, shape=2):
    """ Status of a fetch request that has passed through the IFU. """
    NONE   = 0
    L1_HIT = 1
    L1_MISS = 2
    TLB_MISS = 3

class FetchRequest(Signature):
    """ A request to fetch a cache line at some virtual address. 

    - ``vaddr``:    Virtual address of the requested cacheline
    - ``passthru``: Bypass virtual-to-physical translation

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
    """ Response to a fetch request.  """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(FetchResponseStatus),
            "data": Out(p.l1i.line_layout),
            "ftq_idx": Out(FTQIndex(p)),
        })



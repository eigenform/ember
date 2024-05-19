
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth_soc.wishbone import Interface as WishboneInterface

from ember.common import *
from ember.param import *

from ember.front.fetch import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.front.ftq import *
from ember.front.ifill import *

class EmberFrontend(Component):
    """ Core frontend. 

    Ports
    =====
    fetch_resp: 
        Outgoing bytes from the fetch unit
    alloc_req: 
        Request to allocate an FTQ entry
    fakeram:
        Interface to instruction memory

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "fetch_resp": Out(FetchResponse(param)),
            "alloc_req": In(FTQAllocRequest(param)),
            "fakeram": Out(FakeRamInterface()).array(1),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        ftq   = m.submodules.ftq   = FetchTargetQueue(self.p)
        ifu   = m.submodules.ifu   = FetchUnit(self.p)
        l1i   = m.submodules.l1i   = L1ICache(self.p)
        itlb  = m.submodules.itlb  = L1ICacheTLB(self.p.l1i)
        ifill = m.submodules.ifill = L1IFillUnit(self.p)

        connect(m, ifu.l1i_rp, l1i.rp[0])
        connect(m, ifu.tlb_rp, itlb.rp)
        connect(m, ifu.resp, flipped(self.fetch_resp))
        connect(m, ftq.fetch_req, ifu.req)
        connect(m, ftq.fetch_resp, ifu.resp)
        connect(m, ftq.ifill_resp, ifill.resp)
        connect(m, ftq.alloc_req, flipped(self.alloc_req))

        connect(m, ifu.ifill_req, ifill.req)
        connect(m, ifu.ifill_sts, ifill.sts)
        connect(m, ifill.l1i_wp[0], l1i.wp[0])
        connect(m, ifill.fakeram[0], flipped(self.fakeram[0]))

        return m





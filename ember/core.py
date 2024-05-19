
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

        # Connect the IFU to the L1I and TLB
        connect(m, ifu.l1i_rp, l1i.rp[0])
        connect(m, ifu.tlb_rp, itlb.rp)

        # IFU sends requests to IFILL
        connect(m, ifu.ifill_req, ifill.req)
        connect(m, ifill.sts, ifu.ifill_sts)

        # IFU sends fetched bytes 
        connect(m, ifu.resp, flipped(self.fetch_resp))
        # IFU signalling back to the FTQ
        connect(m, ifu.resp, ftq.fetch_resp)

        # Allocation requests to the FTQ
        connect(m, flipped(self.alloc_req), ftq.alloc_req)
        # FTQ sends requests to the IFU
        connect(m, ftq.fetch_req, ifu.req)
        # Fill unit wakes up FTQ entries for replay
        connect(m, ifill.resp, ftq.ifill_resp)

        # Connect the fill unit to the L1I and memory interfaces
        connect(m, ifill.l1i_wp[0], l1i.wp[0])
        connect(m, ifill.fakeram[0], flipped(self.fakeram[0]))

        return m





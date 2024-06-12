from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum

from ember.common import *
from ember.common.pipeline import *
from ember.common.coding import ChainedPriorityEncoder
from ember.param import *
from ember.front.predecode import *
from ember.uarch.fetch import *
from ember.front.cfc import ControlFlowRequest


class BranchPredictionUnit(Component):
    """ Branch prediction unit. 

    Ports
    =====
    pd_resp:
        A predecoded cacheline from the PDU
    cf_req: 
        Output speculative control-flow request

    """
    def __init__(self, param: EmberParams): 
        self.p = param
        super().__init__(Signature({
            "pd_resp": In(PredecodeResponse(param)),
            "cf_req": Out(ControlFlowRequest(param)),
        }))

    def elaborate(self, platform):
        m = Module()

        pd_width = self.p.l1i.line_depth

        pd_vaddr = self.pd_resp.vaddr
        pd_info = self.pd_resp.info
        pd_info_valid = self.pd_resp.info_valid

        # Determine which entries are valid control-flow instructions
        is_cf = Array(Signal() for idx in range(pd_width))
        for idx in range(pd_width):
            m.d.comb += is_cf[idx].eq(
                pd_info[idx].is_cf & pd_info_valid[idx]
            )

        is_cf = [ self.pd_resp.info[idx].is_cf for idx in range(pd_width) ]

        # Select up to N predecoded control-flow instructions
        pd_sel_enc = m.submodules.pd_sel_enc = \
            ChainedPriorityEncoder(width=pd_width, depth=2)
        m.d.comb += pd_sel_enc.i.eq(Cat(*is_cf))

        m.d.comb += [
            self.cf_req.valid.eq(0),
            self.cf_req.pc.eq(0),
        ]

        return m




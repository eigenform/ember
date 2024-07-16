
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth.lib.coding import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2
from amaranth.back import verilog

from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Signature as WishboneSignature

from ember.common import *
from ember.common.lfsr import LFSR
from ember.riscv.paging import *
from ember.param import *


class L1ICacheTLBReadPort(Signature):
    """ L1I TLB read port. """
    class Request(Signature):
        """ A request to L1I TLB to resolve the physical page number
        for the provided virtual page number. 
        """
        def __init__(self):
            super().__init__({
                'valid': Out(1),
                'vpn': Out(VirtualPageNumberSv32()),
            })
    class Response(Signature):
        """ A response from the L1I TLB containing a physical page number. """
        def __init__(self):
            super().__init__({
                'valid': Out(1),
                'hit': Out(1),
                'pte': Out(PageTableEntrySv32()),
            })

    def __init__(self):
        super().__init__({
            'req': Out(self.Request()),
            'resp': In(self.Response()),
        })


class L1ICacheTLBFillRequest(Signature):
    """ A request to write an entry into the L1I TLB. """
    def __init__(self):
        super().__init__({
            'valid': Out(1),
            'pte': Out(PageTableEntrySv32()),
            'vpn': Out(VirtualPageNumberSv32()),
        })


class L1ICacheTLB(Component):
    """ L1 instruction cache TLB (translation lookaside buffer).

    This is a small fully-associative cache for page table entries. 
    Each entry in the TLB associates a virtual page number (VPN) to 
    a page table entry (PTE). 

    Replacement Policy
    ==================
    Currently, the replacement policy is *random*. 
    The index for each fill request is generated by an LFSR. 

    At some point, this will probably be replaced with the tree-based 
    pseudo least-recently used (PLRU) policy.

    Ports
    =====
    fill_req: :class:`L1ICacheTLBFillRequest`
        Fill request
    rp: :class:`L1ICacheTLBReadPort`
        Read port
    pp: :class:`L1ICacheTLBReadPort`
        Probe read port

    """

    def __init__(self, param: EmberParams):
        self.p = param
        self.depth = param.l1i.tlb.depth

        #self.lfsr = LFSR(degree=ceil_log2(self.depth))

        signature = Signature({
            "fill_req": In(L1ICacheTLBFillRequest()),
            "rp": In(L1ICacheTLBReadPort()),
            "pp": In(L1ICacheTLBReadPort()),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        # Generates a "random" index for allocations/evictions.
        # FIXME: The tree-based PLRU is probably a more reasonable strategy.
        lfsr_en = self.fill_req.valid
        m.submodules.lfsr = lfsr = \
            EnableInserter(lfsr_en)(LFSR(degree=ceil_log2(self.depth)))
        lfsr_out = lfsr.value

        # Tag and data arrays.
        # FIXME: These are going be turned into a lot of flipflops..
        data_arr  = Array(
            Signal(PageTableEntrySv32(), name=f"data_arr{i}") 
            for i in range(self.depth)
        )
        tag_arr   = Array(
            Signal(VirtualPageNumberSv32(), name=f"tag_arr{i}") 
            for i in range(self.depth)
        )
        valid_arr = Array(Signal() for i in range(self.depth))

        # Match signals
        match_arr_rp = Array(
            Signal(name=f"match_arr_rp_{i}") for i in range(self.depth)
        )
        match_arr_pp = Array(
            Signal(name=f"match_arr_pp_{i}") for i in range(self.depth)
        )

        # Convert match signals (one-hot) into an index into the data array. 
        m.submodules.enc_rp = enc_rp = PriorityEncoder(self.depth)
        m.submodules.enc_pp = enc_pp = PriorityEncoder(self.depth)
        match_hit_rp  = (~enc_rp.n & self.rp.req.valid)
        match_hit_pp  = (~enc_pp.n & self.pp.req.valid)
        match_idx_rp  = enc_rp.o
        match_idx_pp  = enc_pp.o
        match_data_rp = Mux(match_hit_rp, data_arr[match_idx_rp], 0)
        match_data_pp = Mux(match_hit_pp, data_arr[match_idx_pp], 0)

        # Default assignment for the response
        m.d.sync += [
            self.rp.resp.valid.eq(self.rp.req.valid),
            self.rp.resp.hit.eq(0),
            self.rp.resp.pte.eq(0),

            self.pp.resp.valid.eq(self.pp.req.valid),
            self.pp.resp.hit.eq(0),
            self.pp.resp.pte.eq(0),
        ]

        with m.If(self.rp.req.valid):
            # Drive input to all of the comparators
            m.d.comb += [
                match_arr_rp[idx].eq(
                    (tag_arr[idx] == self.rp.req.vpn) & valid_arr[idx]
                )
                for idx in range(self.depth)
            ]
            # Obtain the index of the matching entry (if one exists). 
            m.d.comb += [
                enc_rp.i.eq(Cat(*match_arr_rp))
            ]
            # Data for the matching entry is available on the next cycle.
            m.d.sync += [
                self.rp.resp.hit.eq(match_hit_rp),
                self.rp.resp.pte.eq(match_data_rp),
            ]

        with m.If(self.pp.req.valid):
            # Drive input to all of the comparators
            m.d.comb += [
                match_arr_pp[idx].eq(
                    (tag_arr[idx] == self.pp.req.vpn) & valid_arr[idx]
                )
                for idx in range(self.depth)
            ]
            # Obtain the index of the matching entry (if one exists). 
            m.d.comb += [
                enc_pp.i.eq(Cat(*match_arr_pp))
            ]
            # Data for the matching entry is available on the next cycle.
            m.d.sync += [
                self.pp.resp.hit.eq(match_hit_pp),
                self.pp.resp.pte.eq(match_data_pp),
            ]


        with m.If(self.fill_req.valid):
            m.d.sync += [
                tag_arr[lfsr_out].eq(self.fill_req.vpn),
                data_arr[lfsr_out].eq(self.fill_req.pte),
                valid_arr[lfsr_out].eq(1),
            ]

        return m



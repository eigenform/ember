
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Signature as WishboneSignature

from ember.common import *
from ember.front.l1i_array import *
from ember.riscv.paging import *
from ember.param import *

class L1ICacheProbePort(Signature):
    """ An L1I cache probe port. """
    class Request(Signature):
        """ Request to read all tag ways for some set in the L1I cache.
        """
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "set": Out(ceil_log2(p.l1i.num_sets)),
            })
    class Response(Signature):
        """ Response with all tag ways for a particular set in the L1I cache. 
        """
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "tag_data": Out(p.l1i.tag_layout).array(p.l1i.num_ways),
            })

    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(self.Request(p)),
            "resp": In(self.Response(p)),
        })


class L1ICacheReadPort(Signature):
    """ An L1I cache read port. """
    class Request(Signature):
        """ Request to read all tag/data ways for some set in the L1I cache.
        """
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "set": Out(ceil_log2(p.l1i.num_sets)),
            })
    class Response(Signature):
        """ Response with all tag/data ways for a particular set 
        in the L1I cache. 
        """
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "tag_data": Out(p.l1i.tag_layout).array(p.l1i.num_ways),
                "line_data": Out(p.l1i.line_layout).array(p.l1i.num_ways),
            })

    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(self.Request(p)),
            "resp": In(self.Response(p)),
        })

class L1ICacheWritePort(Signature):
    """ An L1I cache write port. """
    class Request(Signature):
        """ A request to write a particular set/way in the L1I cache. """
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "set": Out(ceil_log2(p.l1i.num_sets)),
                "way": Out(ceil_log2(p.l1i.num_ways)),
                "tag_data": Out(p.l1i.tag_layout),
                "line_data": Out(p.l1i.line_layout),
            })
    class Response(Signature):
        """ Response to a write request. """
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
            })

    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(self.Request(p)),
            "resp": In(self.Response(p)),
        })

class L1ICache(Component):
    """ Backing memory for an L1 instruction cache.

    This module consists of a data array and a tag array. 
    This only implements the *storage* for a [set-associative] 
    virtually-indexed and physically-tagged (VIPT) cache. 
    It does not include any of the logic for tag matching. 

    Read ports are used to read the tags and data for a particular set 
    *across all ways* in the cache. 
    Write ports are used to replace the tag and data for a particular set and
    a particular way. 

    For now, there is only one read port and one write port. 

    Ports 
    =====
    rp: :class:`L1ICacheReadPort`
        Read port. 
    wp: :class:`L1ICacheWritePort`
        Write port. 
    pp: :class:`L1ICacheProbePort`
        Probe read port. 

    """

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "rp": In(L1ICacheReadPort(param)).array(param.l1i.num_rp),
            "wp": In(L1ICacheWritePort(param)).array(param.l1i.num_wp),
            "pp": In(L1ICacheProbePort(param)).array(param.l1i.num_pp),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        data_arr = m.submodules.data_arr = L1ICacheDataArray(self.p)
        tag_arr  = m.submodules.tag_arr  = L1ICacheTagArray(self.p)

        # Read port outputs will be valid on the next cycle
        r_rp_output_valid = Signal()
        r_wp_resp_valid = Signal()
        r_pp_resp_valid = Signal()
        m.d.sync += [ 
            r_rp_output_valid.eq(self.rp[0].req.valid),
            r_wp_resp_valid.eq(self.wp[0].req.valid),
            r_pp_resp_valid.eq(self.pp[0].req.valid),
        ]

        # Read port inputs
        m.d.comb += [
            data_arr.rp.req.valid.eq(self.rp[0].req.valid),
            data_arr.rp.req.set.eq(self.rp[0].req.set),

            tag_arr.rp.req.valid.eq(self.rp[0].req.valid),
            tag_arr.rp.req.set.eq(self.rp[0].req.set),

            tag_arr.pp.req.valid.eq(self.pp[0].req.valid),
            tag_arr.pp.req.set.eq(self.pp[0].req.set),
        ]

        # Write port inputs
        m.d.comb += [
            data_arr.wp.req.valid.eq(self.wp[0].req.valid),
            data_arr.wp.req.way.eq(self.wp[0].req.way),
            data_arr.wp.req.idx.eq(self.wp[0].req.set),
            data_arr.wp.req.data.eq(self.wp[0].req.line_data),

            tag_arr.wp.req.valid.eq(self.wp[0].req.valid),
            tag_arr.wp.req.way.eq(self.wp[0].req.way),
            tag_arr.wp.req.idx.eq(self.wp[0].req.set),
            tag_arr.wp.req.data.eq(self.wp[0].req.tag_data),
        ]

        # Valid signals
        m.d.comb += [ 
            self.rp[0].resp.valid.eq(r_rp_output_valid),
            self.wp[0].resp.valid.eq(r_wp_resp_valid),
            self.pp[0].resp.valid.eq(r_pp_resp_valid),
        ]

        for way_idx in range(self.p.l1i.num_ways):
            m.d.comb += [
                self.rp[0].resp.tag_data[way_idx].eq(
                    tag_arr.rp.resp.data[way_idx]
                ),
                self.rp[0].resp.line_data[way_idx].eq(
                    data_arr.rp.resp.data[way_idx]
                ),
                self.pp[0].resp.tag_data[way_idx].eq(
                    tag_arr.pp.resp.data[way_idx]
                ),
            ]

        return m   


class L1IWaySelect(Component):
    """ L1I cache way select logic. 

    Given a set of tags ``i_tags`` across all ways in a set, determine which
    way matches 

    """
    def __init__(self, num_ways: int, tag_layout: Layout):
        self.num_ways = num_ways
        self.tag_layout = tag_layout
        super().__init__(Signature({
            "i_valid": In(1),
            "i_tag": In(tag_layout),
            "i_tags": In(tag_layout).array(num_ways),
            "o_way": Out(exact_log2(num_ways)),
            "o_hit": Out(1),
            "o_valid": Out(1),
        }))

    def elaborate(self, platform):
        m = Module()

        match_arr = Array(
            Signal(name=f"match_arr{way_idx}") 
            for way_idx in range(self.num_ways)
        )
        for way_idx in range(self.num_ways):
            m.d.comb += [
                match_arr[way_idx].eq(
                    (self.i_tags[way_idx].valid) &
                    (self.i_tag.ppn == self.i_tags[way_idx].ppn)
                )
            ]

        m.submodules.match_encoder = match_encoder = \
                PriorityEncoder(self.num_ways)
        match_hit  = (~match_encoder.n & self.i_valid)
        match_idx  = match_encoder.o
        m.d.comb += [
            match_encoder.i.eq(Cat(*match_arr)),
            self.o_way.eq(match_idx),
            self.o_hit.eq(match_hit),
            self.o_valid.eq(self.i_valid),
        ]
 
        return m




from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Signature as WishboneSignature

from ember.common import *
from ember.common.lfsr import *
from ember.front.l1i_array import *
from ember.riscv.paging import *
from ember.param import *
from ember.uarch.front import *

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
                "tag_data": Out(L1ITag()).array(p.l1i.num_ways),
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
                "tag_data": Out(L1ITag()).array(p.l1i.num_ways),
                "line_data": Out(L1ICacheline(p)).array(p.l1i.num_ways),
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
                "tag_data": Out(L1ITag()),
                "line_data": Out(L1ICacheline(p)),
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
    This only implements the *storage* for a set-associative cache.

    .. note::
        I'm assuming that we're using this to implement a virtually-indexed 
        and physically-tagged (VIPT) cache. This module does not include any 
        of the logic for tag matching, and does not include any of the logic 
        for address translation. 

    Read ports are used to read the tags and data for a particular set 
    *across all ways* in the cache. 
    Write ports are used to replace the tag and data for a particular set and
    a particular way. 

    Probe ports are read ports that yield only the tags [without data] for a 
    particular set across all ways.

    .. note:: 
        The probe ports are supposed to support cases like instruction 
        prefetch, where we only want to determine whether or not a matching
        cacheline exists (and needs to be filled sometime in the future). 

    Replacement
    -----------

    The current replacement policy is *random*. 
    Each write port in this module is associated to an LFSR which generates 
    the way index used to write into the data/tag arrays. 

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
        self.num_rp = param.l1i.num_rp
        self.num_wp = param.l1i.num_wp
        self.num_pp = param.l1i.num_pp
        signature = Signature({
            "rp": In(L1ICacheReadPort(param)).array(param.l1i.num_rp),
            "wp": In(L1ICacheWritePort(param)).array(param.l1i.num_wp),
            "pp": In(L1ICacheProbePort(param)).array(param.l1i.num_pp),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        # Data and tag arrays
        data_arr = m.submodules.data_arr = L1ICacheDataArray(self.p)
        tag_arr  = m.submodules.tag_arr  = L1ICacheTagArray(self.p)

        # Create an LFSR for each write port. 
        # NOTE: The replacement policy is random. 
        lfsr_wp = [ 
            EnableInserter(self.wp[idx].req.valid)(LFSR(degree=4))
            for idx in range(self.num_wp) 
        ]
        for idx in range(self.num_wp):
            m.submodules[f"lfsr_wp{idx}"] = lfsr = lfsr_wp[idx]


        # Outputs for the current request are valid on the next cycle
        for idx in range(self.num_rp):
            m.d.sync += self.rp[idx].resp.valid.eq(self.rp[idx].req.valid)
        for idx in range(self.num_wp):
            m.d.sync += self.wp[idx].resp.valid.eq(self.wp[idx].req.valid)
        for idx in range(self.num_pp):
            m.d.sync += self.pp[idx].resp.valid.eq(self.pp[idx].req.valid)

        # Read port inputs
        for idx in range(self.num_rp):
            m.d.comb += [
                data_arr.rp[idx].req.valid.eq(self.rp[idx].req.valid),
                data_arr.rp[idx].req.set.eq(self.rp[idx].req.set),
                tag_arr.rp[idx].req.valid.eq(self.rp[idx].req.valid),
                tag_arr.rp[idx].req.set.eq(self.rp[idx].req.set),
            ]

        # Probe port inputs
        for idx in range(self.num_pp):
            m.d.comb += [
                tag_arr.pp[idx].req.valid.eq(self.pp[idx].req.valid),
                tag_arr.pp[idx].req.set.eq(self.pp[idx].req.set),
            ]

        
        # Write port inputs
        for idx in range(self.num_wp):
            m.d.comb += [
                data_arr.wp[idx].req.valid.eq(self.wp[idx].req.valid),
                data_arr.wp[idx].req.way.eq(lfsr_wp[idx].value),
                data_arr.wp[idx].req.idx.eq(self.wp[idx].req.set),
                data_arr.wp[idx].req.data.eq(self.wp[idx].req.line_data),

                tag_arr.wp[idx].req.valid.eq(self.wp[idx].req.valid),
                tag_arr.wp[idx].req.way.eq(lfsr_wp[idx].value),
                tag_arr.wp[idx].req.idx.eq(self.wp[idx].req.set),
                tag_arr.wp[idx].req.data.eq(self.wp[idx].req.tag_data),
            ]

        # Read port outputs
        for idx in range(self.num_rp):
            for way_idx in range(self.p.l1i.num_ways):
                m.d.comb += [
                    self.rp[idx].resp.tag_data[way_idx].eq(
                        tag_arr.rp[idx].resp.data[way_idx]
                    ),
                    self.rp[idx].resp.line_data[way_idx].eq(
                        data_arr.rp[idx].resp.data[way_idx]
                    ),
                ]

        # Probe port outputs
        for idx in range(self.num_pp):
            for way_idx in range(self.p.l1i.num_ways):
                m.d.comb += [
                    self.pp[idx].resp.tag_data[way_idx].eq(
                        tag_arr.pp[idx].resp.data[way_idx]
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



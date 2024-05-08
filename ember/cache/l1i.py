
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Signature as WishboneSignature

from ember.common import *
from ember.riscv.paging import *
from ember.param import *

class L1ICacheReadRequest(Signature):
    """ Request to read all tag/data ways for some set in the L1I cache. """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "set": Out(ceil_log2(p.l1i.num_sets)),
        })
class L1ICacheReadResponse(Signature):
    """ Response with all tag/data ways for a particular set in the L1I cache. """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "tag_data": Out(p.l1i.tag_layout).array(p.l1i.num_ways),
            "line_data": Out(p.l1i.line_layout).array(p.l1i.num_ways),
        })
class L1ICacheReadPort(Signature):
    """ An L1I cache read port. """
    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(L1ICacheReadRequest(p)),
            "resp": In(L1ICacheReadResponse(p)),
        })

class L1ICacheWriteRequest(Signature):
    """ A request to write a particular set/way in the L1I cache. """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "set": Out(ceil_log2(p.l1i.num_sets)),
            "way": Out(ceil_log2(p.l1i.num_ways)),
            "tag_data": Out(p.l1i.tag_layout),
            "line_data": Out(p.l1i.line_layout),
        })
class L1ICacheWriteResponse(Signature):
    """ Response to an ::L1ICacheWriteRequest . """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
        })
class L1ICacheWritePort(Signature):
    """ An L1I cache write port. """
    def __init__(self, p: EmberParams):
        super().__init__({
            "req": Out(L1ICacheWriteRequest(p)),
            "resp": In(L1ICacheWriteResponse(p)),
        })


class L1ICacheDataArray(Elaboratable):
    """ L1 instruction cache data array.

    The data array is a memory whose capacity is the number of sets in the 
    L1I cache, and where elements in the array are caches lines.

    Read ports perform reads from particular set across all ways.
    Write ports perform writes to a particular set and way. 
    For now, there is one read port and one write port. 
    """
    def __init__(self, param: L1ICacheParams):
        self.p = param
        self.rp_idx  = Signal(ceil_log2(self.p.num_sets))
        self.rp_en   = Signal()
        self.rp_data = Array(
            Signal(self.p.line_layout) for _ in range(self.p.num_ways)
        )
        self.wp_en   = Signal()
        self.wp_way  = Signal(ceil_log2(self.p.num_ways))
        self.wp_idx  = Signal(ceil_log2(self.p.num_sets))
        self.wp_data = Signal(self.p.line_layout)

    def elaborate(self, platform):
        m = Module()

        for way_idx in range(self.p.num_ways):
            mem = m.submodules[f"mem_data_way{way_idx}"] = memory.Memory(
                shape=unsigned(self.p.line_bits), 
                depth=self.p.num_sets,
                init=[],
            )
            rp = mem.read_port()
            m.d.comb += [
                self.rp_data[way_idx].eq(rp.data),
                rp.en.eq(self.rp_en),
                rp.addr.eq(self.rp_idx),
            ]
            wp = mem.write_port()
            sel_way = Signal(name=f"wp_sel_way{way_idx}")
            m.d.comb += [
                sel_way.eq(self.wp_way == way_idx),
                wp.en.eq(self.wp_en & sel_way),
                wp.addr.eq(Mux(sel_way, self.wp_idx, 0)),
                wp.data.eq(Mux(sel_way, self.wp_data, 0)),
            ]

        return m


class L1ICacheTagArray(Elaboratable):
    """ L1 instruction cache tag array.
    
    The tag array is a memory whose capacity is the number of sets in the 
    L1I cache, and where elements in the array are tags belonging to each way 
    in a set.

    Read ports perform reads from particular set across all ways.
    Write ports perform writes to a particular set and way. 
    For now, there is only one read port and one write port. 
    """
    def __init__(self, param: L1ICacheParams):
        self.p = param

        self.rp_idx  = Signal(ceil_log2(self.p.num_sets))
        self.rp_en   = Signal()
        self.rp_data = Array(
            Signal(self.p.tag_layout) for _ in range(self.p.num_ways)
        )

        self.wp_en   = Signal()
        self.wp_way  = Signal(ceil_log2(self.p.num_ways))
        self.wp_idx  = Signal(ceil_log2(self.p.num_sets))
        self.wp_data = Signal(self.p.tag_layout)

    def elaborate(self, platform):
        m = Module()

        for way_idx in range(self.p.num_ways):
            mem = m.submodules[f"mem_tag_way{way_idx}"] = memory.Memory(
                shape=self.p.tag_layout,
                depth=self.p.num_sets,
                init=[],
            )

            rp = mem.read_port()
            tag_data = Signal(self.p.tag_layout)
            m.d.comb += [
                tag_data.eq(rp.data),
                rp.en.eq(self.rp_en),
                rp.addr.eq(self.rp_idx),
                self.rp_data[way_idx].eq(tag_data),
            ]

            wp = mem.write_port()
            sel_way = Signal(name=f"wp_sel_way{way_idx}")
            m.d.comb += [
                sel_way.eq(self.wp_way == way_idx),
                wp.en.eq(self.wp_en & sel_way),
                wp.addr.eq(Mux(sel_way, self.wp_idx, 0)),
                wp.data.eq(Mux(sel_way, self.wp_data, 0)),
            ]
        return m


class L1ICache(Component):
    """ Backing memory for an L1 instruction cache.

    This module consists of a data array and a tag array. 
    This only implements the *storage* for a [set-associative] 
    virtually-indexed and physically-tagged (VIPT) cache. 
    It does not include any of the logic for tag matching. 

    Read and Write Ports
    ====================
    Read ports are used to read the tags and data for a particular set 
    *across all ways* in the cache. 
    Write ports are used to replace the tag and data for a particular set and
    a particular way. 

    For now, there is only one read port and one write port. 
    """

    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "rp": In(L1ICacheReadPort(param)),
            "wp": In(L1ICacheWritePort(param)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        data_arr = m.submodules.data_arr = L1ICacheDataArray(self.p.l1i)
        tag_arr  = m.submodules.tag_arr  = L1ICacheTagArray(self.p.l1i)

        # Read port outputs will be valid on the next cycle
        r_rp_output_valid = Signal()
        m.d.sync += [ 
            r_rp_output_valid.eq(self.rp.req.valid)
        ]

        # Read port inputs
        m.d.comb += [
            data_arr.rp_en.eq(self.rp.req.valid),
            data_arr.rp_idx.eq(self.rp.req.set),
            tag_arr.rp_en.eq(self.rp.req.valid),
            tag_arr.rp_idx.eq(self.rp.req.set),
        ]

        # Write port inputs
        m.d.comb += [
            data_arr.wp_en.eq(self.wp.req.valid),
            data_arr.wp_way.eq(self.wp.req.way),
            data_arr.wp_idx.eq(self.wp.req.set),
            data_arr.wp_data.eq(self.wp.req.line_data),

            tag_arr.wp_en.eq(self.wp.req.valid),
            tag_arr.wp_way.eq(self.wp.req.way),
            tag_arr.wp_idx.eq(self.wp.req.set),
            tag_arr.wp_data.eq(self.wp.req.tag_data),
        ]

        # Read port outputs
        m.d.comb += [ 
            self.rp.resp.valid.eq(r_rp_output_valid),
        ]
        for way_idx in range(self.p.l1i.num_ways):
            m.d.comb += [
                self.rp.resp.tag_data[way_idx].eq(tag_arr.rp_data[way_idx]),
                self.rp.resp.line_data[way_idx].eq(data_arr.rp_data[way_idx]),
            ]

        return m   



class L1IFillRequest(Signature):
    """ L1 instruction cache fill request """
    def __init__(self, p: EmberParams):
        super().__init__({
            "en": In(1),
            "paddr": In(p.rv.xlen),

        })

class L1IWaySelect(Component):
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

        match_arr = Array(Signal() for way_idx in range(self.num_ways))
        for way_idx in range(self.num_ways):
            m.d.comb += [
                match_arr[way_idx].eq(
                    (self.i_tags[way_idx].valid) &
                    (self.i_tag.ppn == self.i_tags[way_idx].ppn)
                )
            ]

        m.submodules.match_encoder = match_encoder = \
                PriorityEncoder(exact_log2(self.num_ways))
        match_hit  = (~match_encoder.n & self.i_valid)
        match_idx  = match_encoder.o
        m.d.comb += [
            match_encoder.i.eq(Cat(*match_arr)),
            self.o_way.eq(match_idx),
            self.o_hit.eq(match_hit),
            self.o_valid.eq(self.i_valid),
        ]
 
        return m




class L1IFillUnit(Component):
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "ready": Out(1),
            "l1i_wp": Out(L1ICacheWritePort(param)),

            # Connection to the ibus for L1I cache fills
            "ibus": Out(WishboneSignature(
                addr_width=30, 
                data_width=32,
                granularity=32,
                features=["err", "cti", "bte"]
            )),

        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()
        return m




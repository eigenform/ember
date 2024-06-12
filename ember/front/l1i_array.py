

from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from ember.param import *

class L1IArrayReadPort(Signature):
    class Request(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
                "set": Out(ceil_log2(p.l1i.num_sets)),
            })
    class Response(Signature):
        def __init__(self, p: EmberParams, data_shape: Shape):
            super().__init__({
                "valid": Out(1),
                "data": Out(data_shape).array(p.l1i.num_ways),
            })
    def __init__(self, p: EmberParams, data_shape: Shape):
        super().__init__({
            "req": Out(self.Request(p)),
            "resp": In(self.Response(p, data_shape)),
        })

class L1IArrayWritePort(Signature):
    class Request(Signature):
        def __init__(self, p: EmberParams, data_shape: Shape):
            super().__init__({
                "valid": Out(1),
                "way": Out(ceil_log2(p.l1i.num_ways)),
                "idx": Out(ceil_log2(p.l1i.num_sets)),
                "data": Out(data_shape),
            })
    class Response(Signature):
        def __init__(self, p: EmberParams):
            super().__init__({
                "valid": Out(1),
            })
    def __init__(self, p: EmberParams, data_shape: Shape):
        super().__init__({
            "req": Out(self.Request(p, data_shape)),
            "resp": In(self.Response(p)),
        })




class L1ICacheDataArray(Component):
    """ L1 instruction cache data array.

    The data array is a memory whose capacity is the number of sets in the 
    L1I cache, and where elements in the array are caches lines.

    Read ports perform reads from particular set across all ways.
    Write ports perform writes to a particular set and way. 
    For now, there is one read port and one write port. 

    Ports
    =====
    rp: :class:`L1IArrayReadPort`
        Read port
    wp: :class:`L1IArrayWritePort`
        Write port
    """


    def __init__(self, param: EmberParams):
        self.p = param
        self.num_rp = param.l1i.num_rp
        self.num_wp = param.l1i.num_wp
        sig = Signature({
            "rp": In(L1IArrayReadPort(param, param.l1i.line_layout)).array(self.num_rp),
            "wp": In(L1IArrayWritePort(param, param.l1i.line_layout)).array(self.num_wp),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        for way_idx in range(self.p.l1i.num_ways):
            mem = m.submodules[f"mem_data_way{way_idx}"] = memory.Memory(
                shape=unsigned(self.p.l1i.line_bits), 
                depth=self.p.l1i.num_sets,
                init=[],
            )

            for idx in range(self.num_rp):
                rp = mem.read_port()
                m.d.comb += [
                    self.rp[idx].resp.data[way_idx].eq(rp.data),
                    rp.en.eq(self.rp[idx].req.valid),
                    rp.addr.eq(self.rp[idx].req.set),
                ]

            for idx in range(self.num_wp):
                wp = mem.write_port()
                sel_way = Signal(name=f"wp{idx}_sel_way{way_idx}")
                m.d.comb += [
                    sel_way.eq(self.wp[idx].req.way == way_idx),
                    wp.en.eq(self.wp[idx].req.valid & sel_way),
                    wp.addr.eq(Mux(sel_way, self.wp[idx].req.idx, 0)),
                    wp.data.eq(Mux(sel_way, self.wp[idx].req.data, 0)),
                ]

        return m


class L1ICacheTagArray(Component):
    """ L1 instruction cache tag array.
    
    The tag array is a memory whose capacity is the number of sets in the 
    L1I cache, and where elements in the array are tags belonging to each way 
    in a set.

    Read ports perform reads from particular set across all ways.
    Write ports perform writes to a particular set and way. 
    The probe ports are read ports dedicated for prefetch probes.

    For now, there is only one read port and one write port. 


    Ports
    =====
    rp: :class:`L1IArrayReadPort`
        Read port
    pp: :class:`L1IArrayReadPort`
        Probe read port
    wp: :class:`L1IArrayWritePort`
        Write port
    """
    def __init__(self, param: EmberParams):
        self.p = param
        self.num_rp = param.l1i.num_rp
        self.num_wp = param.l1i.num_wp
        self.num_pp = param.l1i.num_pp

        sig = Signature({
            "rp": In(L1IArrayReadPort(param, param.l1i.tag_layout)).array(self.num_rp),
            "wp": In(L1IArrayWritePort(param, param.l1i.tag_layout)).array(self.num_wp),
            "pp": In(L1IArrayReadPort(param, param.l1i.tag_layout)).array(self.num_pp),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        for way_idx in range(self.p.l1i.num_ways):
            mem = m.submodules[f"mem_tag_way{way_idx}"] = memory.Memory(
                shape=self.p.l1i.tag_layout,
                depth=self.p.l1i.num_sets,
                init=[],
            )

            for idx in range(self.num_rp):
                rp = mem.read_port()
                tag_data = Signal(self.p.l1i.tag_layout)
                m.d.comb += [
                    tag_data.eq(rp.data),
                    rp.en.eq(self.rp[idx].req.valid),
                    rp.addr.eq(self.rp[idx].req.set),
                    self.rp[idx].resp.data[way_idx].eq(tag_data),
                ]

            for idx in range(self.num_pp):
                pp = mem.read_port()
                tag_data = Signal(self.p.l1i.tag_layout)
                m.d.comb += [
                    tag_data.eq(pp.data),
                    pp.en.eq(self.pp[idx].req.valid),
                    pp.addr.eq(self.pp[idx].req.set),
                    self.pp[idx].resp.data[way_idx].eq(tag_data),
                ]


            for idx in range(self.num_wp):
                wp = mem.write_port()
                sel_way = Signal(name=f"wp{idx}_sel_way{way_idx}")
                m.d.comb += [
                    sel_way.eq(self.wp[idx].req.way == way_idx),
                    wp.en.eq(self.wp[idx].req.valid & sel_way),
                    wp.addr.eq(Mux(sel_way, self.wp[idx].req.idx, 0)),
                    wp.data.eq(Mux(sel_way, self.wp[idx].req.data, 0)),
                ]
        return m




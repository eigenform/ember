
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2

class BCAMReadPort(Signature):
    def __init__(self, tag_layout, data_layout):
        super().__init__({
            "en": In(1),
            "tag": In(tag_layout),

            "hit": Out(1),
            "data": Out(data_layout),
        })

class BCAMWritePort(Signature):
    def __init__(self, tag_layout, data_layout):
        super().__init__({
            "en": In(1),
            "tag": In(tag_layout),
            "data": In(data_layout),
        })

class GenericBCAM(Component):
    """ Binary content addressable memory (BCAM) with synchronous read.

    Read Ports
    ==========
    - Cycle 1
        - Capture input
    - Cycle 2: 

        - Capture match array
    - Cycle 3: 
        - Capture match data

    """
    def __init__(self, tag_layout, data_layout, depth: int):
        self.tag_layout = tag_layout
        self.data_layout = data_layout
        self.depth = depth
        signature = Signature({
            "rp": In(BCAMReadPort(tag_layout, data_layout)),
            "wp": In(BCAMWritePort(tag_layout, data_layout)),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        # Registers describing which entries are matching
        match_arr = Array(Signal() for _ in range(self.depth))
        # Registers describing which entries are valid/in-use
        valid_arr = Array(Signal() for _ in range(self.depth))
        # Registers for data
        data_arr  = Array(Signal(self.data_layout) for _ in range(self.depth))
        # Registers for tags
        tag_arr   = Array(Signal(self.tag_layout) for _ in range(self.depth))

        # When writing into the CAM, we need to pick an entry to write/evict. 
        # FIXME: Maybe LFSR is an okay strategy? Or LRU? 
        alloc_encoder = PriorityEncoder(self.depth)
        alloc_idx     = Signal(ceil_log2(self.depth))
        alloc_ok      = Signal()
        m.d.comb += [
            alloc_encoder.i.eq(Cat(*valid_arr)),
        ]
        m.d.sync += [
            alloc_ok.eq(~alloc_encoder.n),
            alloc_idx.eq(alloc_encoder.o),
        ]


        with m.Switch(Cat(self.rp.en, self.wp.en)):
            with m.Case(0b00):
                m.d.sync += [ match[idx].eq(0) for idx in range(self.depth) ]
            with m.Case(0b01):
                m.d.sync += [ match[idx].eq(0) for idx in range(self.depth) ]
            with m.Case(0b10):
                m.d.sync += [ 
                    match[idx].eq(tag_arr[idx] == self.rp.tag)
                    for idx in range(self.depth)
                ]
            with m.Case(0b11):
                m.d.sync += [ 
                    match[idx].eq(tag_arr[idx] == self.rp.tag)
                    for idx in range(self.depth)
                ]

        match_encoder = Encoder(self.depth)
        m.d.comb += [
            match_encoder.i.eq(Cat(*match_arr))
            self.rp.hit.eq(not match_encoder.n),
            self.rp.data.eq(),
        ]


        return m






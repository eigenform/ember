from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *

from amaranth.utils import ceil_log2

#class Parameters(object):
#    def __init__(self, **kwargs):
#        for (k, v) in kwargs.items():
#            self.__setattr__(k, v)


class InstructionBusParams(object):
    """ Memory interface parameters """
    def __init__(self):
        self.data_width = 64
        self.addr_width = 32



class L1ICacheTLBParams(object):
    """ L1 iTLB parameters """
    def __init__(self, num_entries, **kwargs):
        self.num_entries = num_entries
        for (k, v) in kwargs.items():
            self.__setattr__(k, v)


class L1ICacheParams(object):
    """ L1 instruction cache parameters 
    addr_width - Number of bits in a virtual address (XLEN)
    num_sets   - Number of sets
    num_ways   - Number of ways
    word_width - Number of bits in a cache word
    line_depth - Number of words in a cache line
    """
    def __init__(self, addr_width, num_sets, num_ways, word_width, line_depth):
        self.addr_width = addr_width
        self.num_sets   = num_sets
        self.num_ways   = num_ways
        self.word_width = word_width
        self.line_depth = line_depth

        # L1I cache line 
        self.line_bits    = self.word_width * self.line_depth
        self.line_bytes   = self.line_bits // 8

        # For virtual address layout
        self.num_off_bits = ceil_log2(self.line_bytes) - 2
        self.num_idx_bits = ceil_log2(self.num_sets)
        self.num_tag_bits = (
            addr_width - self.num_off_bits - self.num_idx_bits - 2
        )

        # Layout of a virtual address from the perspective of the L1I cache
        self.vaddr_layout = StructLayout({
            'wrd': unsigned(2),
            'off': unsigned(self.num_off_bits),
            'idx': unsigned(self.num_idx_bits),
            'tag': unsigned(self.num_tag_bits),
        })
        assert self.vaddr_layout.size == self.addr_width

        # Layout of an L1I cache line
        self.line_layout = ArrayLayout(
            unsigned(self.word_width), 
            self.line_depth
        )

        # Layout of an L1I tag
        self.tag_layout  = StructLayout({
            "valid": unsigned(1),
            "tag": unsigned(self.num_tag_bits)
        })

        # TLB parameters
        self.tlb = L1ICacheTLBParams(
            num_entries=16,
        )



class EmberParams:
    """ Top-level parameters """
    xlen = 32
    xlen_bits = xlen
    xlen_bytes = xlen_bits // 8

    # The reset vector can be implementation-defined. 
    # I guess this is fine for now. 
    reset_vector = 0x0000_0000

    # Sv32 only uses 4KiB pages (???)
    page_size_bytes = 0x0000_1000

    # Number of instructions fetched per cycle
    fetch_width = 4
    fetch_bytes = xlen_bytes * fetch_width

    # The number of low-order offset bits in a fetch address
    fetch_offset_bits = ceil_log2(fetch_bytes)

    ibus = InstructionBusParams()

    # L1 Instruction Cache parameters
    l1i = L1ICacheParams(
        addr_width=xlen_bits,
        num_sets=32,
        num_ways=2,
        word_width=xlen_bits,
        line_depth=fetch_width
    )




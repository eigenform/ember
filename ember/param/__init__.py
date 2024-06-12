from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *

from amaranth.utils import ceil_log2

from ember.riscv.inst import *
from ember.riscv.paging import *
from ember.uarch.mop import *
from ember.uarch.addr import *

#class Parameters(object):
#    def __init__(self, **kwargs):
#        for (k, v) in kwargs.items():
#            self.__setattr__(k, v)

class RiscvParams(object):
    """ RISC-V ISA parameters. 

    Attributes
    ==========
    reset_vector:
        The program counter value on reset

    """
    xlen         = 32
    xlen_bits    = xlen
    xlen_bytes   = (xlen_bits // 8)

    # NOTE: The reset vector is implementation-defined.
    reset_vector = 0x0000_0000

    # Sv32 only uses 4KiB pages (???)
    page_size_bytes = 0x0000_1000



class InstructionBusParams(object):
    """ Memory interface parameters.
    """
    def __init__(self):
        self.data_width = 64
        self.addr_width = 32



class L1ICacheTLBParams(object):
    """ L1 iTLB parameters. 

    - ``num_entries`` - Number of TLB entries 
    """
    def __init__(self, num_entries: int, **kwargs):
        self.num_entries = num_entries
        for (k, v) in kwargs.items():
            self.__setattr__(k, v)

class L1IFillParams(object):
    def __init__(self, **kwargs):
        for (k, v) in kwargs.items():
            self.__setattr__(k, v)


class L1ICacheParams(object):
    """ L1 instruction cache parameters.

    Parameters
    ==========
    num_sets: 
        Number of sets
    num_ways: 
        Number of ways
    word_width: 
        Number of bits in a cache word
    line_depth: 
        Number of words in a cache line
    """
    def __init__(self, rv: RiscvParams, 
                 word_width: int, 
                 num_sets: int, num_ways: int, 
                 line_depth: int):
        self.addr_width = rv.xlen_bits
        self.word_width = word_width
        self.num_sets   = num_sets
        self.num_ways   = num_ways
        self.line_depth = line_depth

        #self.num_banks = 4


        self.num_rp = 1
        self.num_wp = 2
        self.num_pp = 1

        # L1I cache line 
        self.line_bits    = self.word_width * self.line_depth
        self.line_bytes   = self.line_bits // 8

        # For virtual address layout
        self.num_off_bits = ceil_log2(self.line_bytes) - 2
        self.num_idx_bits = ceil_log2(self.num_sets)
        self.num_tag_bits = (
            self.addr_width - self.num_off_bits - self.num_idx_bits - 2
        )

        # Layout of a virtual address from the perspective of the L1I cache
        # FIXME: deprecated
        #self.vaddr_layout = StructLayout({
        #    'wrd': unsigned(2),
        #    'off': unsigned(self.num_off_bits),
        #    'idx': unsigned(self.num_idx_bits),
        #    'tag': unsigned(self.num_tag_bits),
        #})
        #assert self.vaddr_layout.size == self.addr_width

        # Layout of an L1I cache line
        self.line_layout = ArrayLayout(
            unsigned(self.word_width), 
            self.line_depth
        )

        # Layout of an L1I tag
        self.tag_layout  = StructLayout({
            "valid": unsigned(1),
            "ppn": PhysicalPageNumberSv32(),
        })

        # TLB parameters
        self.tlb = L1ICacheTLBParams(
            num_entries=8,
        )

        self.fill = L1IFillParams(
            num_mshr=2,
        )


class FetchParams(object):
    """ Instruction fetch parameters.

    Parameters
    ==========
    width:
        Number of instructions fetched per cycle

    """
    def __init__(self, rv: RiscvParams, width: int): 
        # Number of Fetch Target Queue entries
        self.ftq_depth  = 8
        # Number of *instructions* fetched per cycle. 
        self.width = width
        # Number of *bytes* fetched per cycle. 
        self.width_bytes = width * rv.xlen_bytes
        # Number of low-order offset bits in a fetch address
        self.offset_bits = ceil_log2(self.width_bytes)

class BranchPredictionParams(object):
    def __init__(self, vaddr: VirtualAddress):
        self.l0_btb_tag_shape = unsigned(vaddr.num_blk_bits)



class DecodeParams(object):
    """ Instruction decode parameters.

    Parameters
    ==========
    width:
        Number of instructions decoded per cycle

    """
    def __init__(self, rv: RiscvParams, width: int):
        self.width = width

class EmberParams:
    """ Top-level parameters. 

    For now, users are expected to manually change values in this class. 
    At some point, we ideally want this to be an object that a user can 
    construct and override while elaborating the design.

    Attributes
    ==========
    superscalar_width:
        The width of the instruction pipeline (in number of instructions).

    inst: :class:`RvInstGroup`
        The set of supported RISC-V instructions
    mops: :class:`EmberMopGroup`
        The set of supported macro-ops
    vaddr: VirtualAddress
        The layout for a virtual address.
    paddr: PhysicalAddress
        The layout for a physical address.

    """

    # RISC-V ISA parameters
    rv = RiscvParams()

    superscalar_width = 8
    inst: RvInstGroup   = RV32I_BASE_SET
    mops: EmberMopGroup = DEFAULT_EMBER_MOPS

    # Module-specific parameters
    l1i = L1ICacheParams(rv,
        num_sets=32,
        num_ways=2,
        word_width=32,
        line_depth=8,
    )

    vaddr = VirtualAddress(
        l1i_line_bytes=l1i.line_bytes,
        l1i_num_sets=l1i.num_sets
    )
    paddr = PhysicalAddress(
        l1i_line_bytes=l1i.line_bytes,
        l1i_num_sets=l1i.num_sets
    )

    bp     = BranchPredictionParams(vaddr)
    fetch  = FetchParams(rv, width=superscalar_width)
    decode = DecodeParams(rv, width=superscalar_width)
    ibus   = InstructionBusParams()




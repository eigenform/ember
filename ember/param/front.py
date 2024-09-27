
from ember.param.riscv import *
from ember.uarch.addr import *
from ember.riscv.paging import *

class InstructionBusParams(object):
    """ Memory interface parameters.
    """
    def __init__(self):
        self.data_width = 64
        self.addr_width = 32

class L1ICacheTLBParams(object):
    """ L1 iTLB parameters. 
    """
    def __init__(self): 
        self.depth = 32
        #self.data_shape = PageTableEntrySv32()
        #self.tag_shape  = VirtualPageNumberSv32()

class L1IFillParams(object):
    def __init__(self, num_mshr: int, num_port: int, **kwargs):
        self.num_mshr = num_mshr
        self.num_port = num_mshr


class L1ICacheParams(object):
    """ L1 instruction cache parameters.

    Depends on an instance of :class:`RiscvParams`. 

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

        #self.way_idx_shape = unsigned(exact_log2(num_ways))
        #self.set_idx_shape = unsigned(exact_log2(num_sets))

        # L1I cache line 
        self.line_bits    = self.word_width * self.line_depth
        self.line_bytes   = self.line_bits // 8

        # For virtual address layout
        self.num_off_bits = ceil_log2(self.line_bytes) - 2
        self.num_idx_bits = ceil_log2(self.num_sets)
        self.num_tag_bits = (
            self.addr_width - self.num_off_bits - self.num_idx_bits - 2
        )

        # Ports
        self.num_rp = 1
        self.num_wp = 2
        self.num_pp = 1

        # Layout of an L1I cache line
        #self.line_layout = ArrayLayout(
        #    unsigned(self.word_width), 
        #    self.line_depth
        #)

        ## Layout of an L1I tag
        #self.tag_layout  = StructLayout({
        #    "valid": unsigned(1),
        #    "ppn": PhysicalPageNumberSv32(),
        #})

        # L1I TLB parameters
        self.tlb = L1ICacheTLBParams()

        # L1I fill parameters
        self.fill = L1IFillParams(
            num_mshr=2,
            num_port=2,
        )


class FTQParams(object):
    def __init__(self): 
        self.depth = 16
        self.index_shape = unsigned(exact_log2(self.depth))

class FetchParams(object):
    """ Instruction fetch parameters.

    Depends on an instance of :class:`RiscvParams`. 

    Parameters
    ==========
    width:
        Number of instructions fetched per cycle

    """
    def __init__(self, rv: RiscvParams, width: int): 
        # Number of *instructions* fetched per cycle. 
        self.width = width
        # Number of *bytes* fetched per cycle. 
        self.width_bytes = width * rv.xlen_bytes
        # Number of low-order offset bits in a fetch address
        self.offset_bits = ceil_log2(self.width_bytes)

class L0BTBParams(object):
    def __init__(self):
        self.depth = 16


class BranchPredictionParams(object):
    """ Branch prediction parameters.

    Depends on an instance of :class:`L1ICacheParams` and :class:`VirtualAddress`. 

    Parameters
    ==========

    """
    def __init__(self):
        self.l0_btb = L0BTBParams()





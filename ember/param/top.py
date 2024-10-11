from abc import abstractmethod, ABCMeta, ABC

from amaranth import *
from amaranth import ShapeLike
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *

from amaranth.utils import ceil_log2

from ember.riscv.inst import *
from ember.riscv.paging import *

from ember.uarch.mop import *
from ember.uarch.addr import *


from ember.param.riscv import *
from ember.param.front import *
from ember.param.midcore import *
from ember.param.back import *

class EmberParams:
    """ Top-level parameters. 

    For now, users are expected to manually change values in this class. 
    At some point, we ideally want this to be an object that a user can 
    construct and override while elaborating the design.

    .. warning:
        It's useful to use this object as a container for different *types* 
        (`ShapeLike` or `ShapeCastable` objects) that are instantiated before
        actually elaborating components in the design.

        In that case, you may need to do some footwork to avoid creating 
        circular dependencies involving this class, ie. making sure that an
        instance of this class is evaluated *before* elaboration. 

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

    l1i: L1ICacheParams
        L1I cache parameters
    bp: BranchPredictionParams
        Branch prediction parameters
    ftq: FTQParams
        FTQ parameters
    fetch: FetchParams
        Instruction fetch parameters
    decode: DecodeParams
        Instruction decode parameters
    ibus: InstructionBusParams
        Instruction bus parameters

    """

    def __init__(self):
        # RISC-V ISA parameters
        self.rv = RiscvParams()

        self.superscalar_width: int = 8
        self.inst: RvInstGroup   = RV32I_BASE_SET
        self.mops: EmberMopGroup = DEFAULT_EMBER_MOPS

        # Maximum size of a "fetch block" (number of sequential cachelines)
        self.max_fblk_size = 16
        self.fblk_size_shape = unsigned(exact_log2(self.max_fblk_size))

        # L1I cache parameters. 
        self.l1i = L1ICacheParams(self.rv,
            num_sets=32,
            num_ways=2,
            word_width=32,
            line_depth=8,
        )

        # Virtual address layout
        self.vaddr = VirtualAddress(
            l1i_line_bytes=self.l1i.line_bytes,
            l1i_num_sets=self.l1i.num_sets
        )

        # Physical address layout
        self.paddr = PhysicalAddress(
            l1i_line_bytes=self.l1i.line_bytes,
            l1i_num_sets=self.l1i.num_sets
        )

        self.bp     = BranchPredictionParams()
        self.ftq    = FTQParams()
        self.fetch  = FetchParams(self.rv, width=self.superscalar_width)
        self.decode = DecodeParams(self.rv, width=self.superscalar_width)
        self.ibus   = InstructionBusParams()




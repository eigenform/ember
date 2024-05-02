from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *

from amaranth.utils import ceil_log2

from ember.riscv.inst import *
from ember.uarch.mop import *

#class Parameters(object):
#    def __init__(self, **kwargs):
#        for (k, v) in kwargs.items():
#            self.__setattr__(k, v)


class InstructionBusParams(object):
    """ Memory interface parameters.
    """
    def __init__(self):
        self.data_width = 64
        self.addr_width = 32



class L1ICacheTLBParams(object):
    """ L1 iTLB parameters. 
    """
    def __init__(self, num_entries, **kwargs):
        self.num_entries = num_entries
        for (k, v) in kwargs.items():
            self.__setattr__(k, v)


class L1ICacheParams(object):
    """ L1 instruction cache parameters.

    - ``addr_width`` - Number of bits in a virtual address (XLEN)
    - ``num_sets``   - Number of sets
    - ``num_ways``   - Number of ways
    - ``word_width`` - Number of bits in a cache word
    - ``line_depth`` - Number of words in a cache line
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

class DecodeParams(object):
    # The group of supported RISC-V instructions
    inst_group = RV32I_BASE_SET

    # The group of macro-ops mapped to all supported instructions
    mop_group = EmberMopGroup(members={
        "AUIPC": EmberMop(RvFormat.U, alloc=1, alu_op=AluOp.ADD,
                         dst=DestOperand.RD, src1=SourceOperand.PC, src2=SourceOperand.IMM),
        "LUI":  EmberMop(RvFormat.U, alloc=1, alu_op=AluOp.ADD, dst=DestOperand.RD),

        "JAL":  EmberMop(RvFormat.J, jmp_op=JmpOp.JAL, dst=DestOperand.PC),
        "JALR": EmberMop(RvFormat.I, alloc=1, jmp_op=JmpOp.JALR, dst=DestOperand.RD|DestOperand.PC),

        "BEQ":  EmberMop(RvFormat.B, brn_op=BrnOp.EQ, dst=DestOperand.PC,),
        "BNE":  EmberMop(RvFormat.B, brn_op=BrnOp.NE, dst=DestOperand.PC,),
        "BLT":  EmberMop(RvFormat.B, brn_op=BrnOp.LT, dst=DestOperand.PC,),
        "BGE":  EmberMop(RvFormat.B, brn_op=BrnOp.GE, dst=DestOperand.PC,),
        "BLTU": EmberMop(RvFormat.B, brn_op=BrnOp.LTU, dst=DestOperand.PC,),
        "BGEU": EmberMop(RvFormat.B, brn_op=BrnOp.GEU, dst=DestOperand.PC,),

        "LB":   EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.B, dst=DestOperand.RD,),
        "LH":   EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.H, dst=DestOperand.RD,),
        "LW":   EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.W, dst=DestOperand.RD,),
        "LBU":  EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.BU, dst=DestOperand.RD,),
        "LHU":  EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.HU, dst=DestOperand.RD,),

        "SB":   EmberMop(RvFormat.S, st_op=StoreOp.B, dst=DestOperand.MEM,),
        "SH":   EmberMop(RvFormat.S, st_op=StoreOp.H, dst=DestOperand.MEM,),
        "SW":   EmberMop(RvFormat.S, st_op=StoreOp.W, dst=DestOperand.MEM,),

        "ADDI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.ADD, dst=DestOperand.RD,),
        "SLTI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SLT, dst=DestOperand.RD,),
        "SLTIU": EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SLTU, dst=DestOperand.RD,),
        "XORI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.XOR, dst=DestOperand.RD,),
        "ORI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.OR, dst=DestOperand.RD,),
        "ANDI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.AND, dst=DestOperand.RD,),
        "SLLI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SLL, dst=DestOperand.RD,),
        "SRLI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SRL, dst=DestOperand.RD,),
        "SRAI":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SRA, dst=DestOperand.RD,),

        "ADD":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.ADD, dst=DestOperand.RD,),
        "SUB":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SUB, dst=DestOperand.RD,),
        "SLL":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SLL, dst=DestOperand.RD,),
        "SLT":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SLT, dst=DestOperand.RD,),
        "SLTU": EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SLTU, dst=DestOperand.RD,),
        "XOR":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.XOR, dst=DestOperand.RD,),
        "SRL":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SRL, dst=DestOperand.RD,),
        "SRA":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SRA, dst=DestOperand.RD,),
        "OR":   EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.OR, dst=DestOperand.RD,),
        "AND":  EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.AND, dst=DestOperand.RD,),

        "FENCE":  EmberMop(RvFormat.I, sys_op=SysOp.FENCE),
        "ECALL":  EmberMop(RvFormat.I, sys_op=SysOp.ECALL),
        "EBREAK": EmberMop(RvFormat.I, sys_op=SysOp.EBREAK),
    })



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

    decode = DecodeParams()

    iset = RV32I_BASE_SET

    ibus = InstructionBusParams()

    # L1 Instruction Cache parameters
    l1i = L1ICacheParams(
        addr_width=xlen_bits,
        num_sets=32,
        num_ways=2,
        word_width=xlen_bits,
        line_depth=fetch_width
    )




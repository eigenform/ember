from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *

from ember.riscv.inst import *
from ember.riscv.encoding import *

class DestOperand(Flag):
    NONE = 0b0000
    RD   = 0b0001
    MEM  = 0b0010
    CSR  = 0b0100
    PC   = 0b1000

class SourceOperand(Enum):
    ZERO = 0b0000
    RS1  = 0b0001
    RS2  = 0b0010
    IMM  = 0b0100
    PC   = 0b1000

class AluOp(Enum):
    NONE = 0b0000
    ADD  = 0b0001
    SUB  = 0b0010
    AND  = 0b0011
    OR   = 0b0100
    XOR  = 0b0101
    SLT  = 0b0110
    SLTU = 0b0111
    SLL  = 0b1001
    SRL  = 0b1010
    SRA  = 0b1011

class BrnOp(Enum):
    NONE = 0b000
    EQ   = 0b001
    NE   = 0b010
    LT   = 0b011
    GE   = 0b100
    LTU  = 0b101
    GEU  = 0b110

class LoadOp(Enum):
    NONE = 0
    B    = 1 
    H    = 2 
    W    = 3 
    BU   = 4 
    HU   = 5 

class StoreOp(Enum):
    NONE = 0
    B = 1
    H = 2
    W = 3

class SysOp(Enum):
    NONE   = 0
    FENCE  = 1
    ECALL  = 2
    EBREAK = 3
    CSRRW  = 4
    CSRRS  = 5
    CSRRC  = 6

class JmpOp(Enum):
    NONE = 0b00
    JAL  = 0b01
    JALR = 0b10

class EmberMop(object):
    layout = StructLayout({
        "fmt": RvFormat,
        "src1": SourceOperand,
        "src2": SourceOperand,
        "alu_op": AluOp,
        "brn_op": BrnOp,
        "jmp_op": JmpOp,
        "sys_op": SysOp,
        "ld_op": LoadOp,
        "st_op": StoreOp,
        "alloc": unsigned(1),
    })
    def __init__(self, fmt: RvFormat, 
                 alloc: int = 0,
                 dst: DestOperand = DestOperand.NONE,
                 src1: SourceOperand = SourceOperand.ZERO,
                 src2: SourceOperand = SourceOperand.ZERO,
                 alu_op: AluOp = AluOp.NONE,
                 brn_op: BrnOp = BrnOp.NONE,
                 jmp_op: JmpOp = JmpOp.NONE,
                 sys_op: SysOp = SysOp.NONE,
                 ld_op: LoadOp = LoadOp.NONE,
                 st_op: StoreOp = StoreOp.NONE,
                 ):
        self.values = {
            "alloc": alloc,
            "fmt": fmt,
            "src1": src1.value,
            "src2": src2.value,
            "alu_op": alu_op.value,
            "brn_op": brn_op.value,
            "jmp_op": jmp_op.value,
            "sys_op": sys_op.value,
            "ld_op": ld_op.value,
            "st_op": st_op.value,
        }

    def as_const(self): 
        return C(self.values, self.layout)

class EmberMopGroup(object):
    def __init__(self, members={}):
        self.members = members
    def items(self):
        return self.members.items()
    def get_mop_by_name(self, mnemonic):
        return self.members[mnemonic]
    def get_const_by_name(self, mnemonic):
        return self.members[mnemonic].as_const()


DEFAULT_EMBER_MOPS = EmberMopGroup(members={
    "AUIPC":  EmberMop(RvFormat.U, alloc=1, alu_op=AluOp.ADD,
                      dst=DestOperand.RD, src1=SourceOperand.PC, src2=SourceOperand.IMM),
    "LUI":    EmberMop(RvFormat.U, alloc=1, alu_op=AluOp.ADD, dst=DestOperand.RD),

    "JAL":    EmberMop(RvFormat.J, jmp_op=JmpOp.JAL, dst=DestOperand.PC),
    "JALR":   EmberMop(RvFormat.I, alloc=1, jmp_op=JmpOp.JALR, dst=DestOperand.RD|DestOperand.PC),
    "BEQ":    EmberMop(RvFormat.B, brn_op=BrnOp.EQ, dst=DestOperand.PC,),
    "BNE":    EmberMop(RvFormat.B, brn_op=BrnOp.NE, dst=DestOperand.PC,),
    "BLT":    EmberMop(RvFormat.B, brn_op=BrnOp.LT, dst=DestOperand.PC,),
    "BGE":    EmberMop(RvFormat.B, brn_op=BrnOp.GE, dst=DestOperand.PC,),
    "BLTU":   EmberMop(RvFormat.B, brn_op=BrnOp.LTU, dst=DestOperand.PC,),
    "BGEU":   EmberMop(RvFormat.B, brn_op=BrnOp.GEU, dst=DestOperand.PC,),

    "LB":     EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.B, dst=DestOperand.RD,),
    "LH":     EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.H, dst=DestOperand.RD,),
    "LW":     EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.W, dst=DestOperand.RD,),
    "LBU":    EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.BU, dst=DestOperand.RD,),
    "LHU":    EmberMop(RvFormat.I, alloc=1, ld_op=LoadOp.HU, dst=DestOperand.RD,),

    "SB":     EmberMop(RvFormat.S, st_op=StoreOp.B, dst=DestOperand.MEM,),
    "SH":     EmberMop(RvFormat.S, st_op=StoreOp.H, dst=DestOperand.MEM,),
    "SW":     EmberMop(RvFormat.S, st_op=StoreOp.W, dst=DestOperand.MEM,),

    "ADDI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.ADD, dst=DestOperand.RD,),
    "SLTI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SLT, dst=DestOperand.RD,),
    "SLTIU":  EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SLTU, dst=DestOperand.RD,),
    "XORI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.XOR, dst=DestOperand.RD,),
    "ORI":    EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.OR, dst=DestOperand.RD,),
    "ANDI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.AND, dst=DestOperand.RD,),
    "SLLI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SLL, dst=DestOperand.RD,),
    "SRLI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SRL, dst=DestOperand.RD,),
    "SRAI":   EmberMop(RvFormat.I, alloc=1, alu_op=AluOp.SRA, dst=DestOperand.RD,),

    "ADD":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.ADD, dst=DestOperand.RD,),
    "SUB":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SUB, dst=DestOperand.RD,),
    "SLL":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SLL, dst=DestOperand.RD,),
    "SLT":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SLT, dst=DestOperand.RD,),
    "SLTU":   EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SLTU, dst=DestOperand.RD,),
    "XOR":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.XOR, dst=DestOperand.RD,),
    "SRL":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SRL, dst=DestOperand.RD,),
    "SRA":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.SRA, dst=DestOperand.RD,),
    "OR":     EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.OR, dst=DestOperand.RD,),
    "AND":    EmberMop(RvFormat.R, alloc=1, alu_op=AluOp.AND, dst=DestOperand.RD,),

    "FENCE":  EmberMop(RvFormat.I, sys_op=SysOp.FENCE),
    "ECALL":  EmberMop(RvFormat.I, sys_op=SysOp.ECALL),
    "EBREAK": EmberMop(RvFormat.I, sys_op=SysOp.EBREAK),
})




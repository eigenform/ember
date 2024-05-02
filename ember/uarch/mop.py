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




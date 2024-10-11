from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *

from ember.riscv.inst import *
from ember.riscv.encoding import *

class DestOperand(Flag, shape=4):
    """ Destination operand types

    Values
    ======
    NONE: 
        No destination operand
    RD:
        Writes to a general-purpose register
    MEM:
        Writes to memory
    CSR:
        Writes to a control/status register
    PC:
        Writes to the program counter
    """
    NONE = 0b0000
    RD   = 0b0001
    MEM  = 0b0010
    CSR  = 0b0100
    PC   = 0b1000

class SourceOperand(Enum, shape=4):
    """ Source operand types

    Values
    ======
    ZERO:
        A value of 'zero'
    RS1:
        Source register 1
    RS2:
        Source register 2
    IMM:
        Immediate value
    PC:
        Program counter
    """
    ZERO = 0b0000
    RS1  = 0b0001
    RS2  = 0b0010
    IMM  = 0b0100
    PC   = 0b1000

class AluOp(Enum, shape=4):
    """ ALU operations

    Values
    ======
    NONE:
        No ALU operation
    ADD:
        Addition
    SUB:
        Subtraction
    AND:
        Logical AND
    OR:
        Logical OR
    XOR:
        Logical XOR
    SLT:
        Signed comparison (less-than)
    SLTU:
        Unsigned comparison (less-than)
    SLL:
        Shift left (logical)
    SRL:
        Shift right (logical)
    SRA:
        Shift right (arithmetic)
    """
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

class BrnOp(Enum, shape=3):
    """ Branch operations

    Values
    ======
    NONE:
        No branch operation
    EQ: 
        Branch if equal
    NE: 
        Branch if not equal
    LT: 
        Branch if less-than (signed)
    GE: 
        Branch if greater-than (signed)
    LTU:
        Branch if less-than (unsigned)
    GEU:
        Branch if greater-than (unsigned)
    """
    NONE = 0b000
    EQ   = 0b001
    NE   = 0b010
    LT   = 0b011
    GE   = 0b100
    LTU  = 0b101
    GEU  = 0b110

class LoadOp(Enum, shape=3):
    """ Load operation

    Values
    ======
    NONE:
        No load operation
    B:
        Load byte (8-bit), zero-extended to 32-bit
    H:
        Load half-word (16-bit), zero-extended to 32-bit
    W:
        Load word (32-bit)
    BU:
        Load byte (8-bit), sign-extended to 32-bit
    HU:
        Load half-word (16-bit), sign-extended to 32-bit
    """
    NONE = 0
    B    = 1 
    H    = 2 
    W    = 3 
    BU   = 4 
    HU   = 5 

class StoreOp(Enum, shape=2):
    """ Store operation

    Values
    ======
    NONE:
        No store operation
    B:
        Store byte (8-bit)
    H:
        Store half-word (16-bit)
    W:
        Store word (32-bit)
    """
    NONE = 0
    B = 1
    H = 2
    W = 3

class SysOp(Enum, shape=3):
    NONE   = 0
    FENCE  = 1
    ECALL  = 2
    EBREAK = 3
    CSRRW  = 4
    CSRRS  = 5
    CSRRC  = 6

class JmpOp(Enum, shape=2):
    NONE = 0b00
    JAL  = 0b01
    JALR = 0b10

class ControlFlowOp(Enum, shape=3):
    NONE     = 0b000
    BRANCH   = 0b001
    JUMP_DIR = 0b010
    JUMP_IND = 0b011
    CALL_DIR = 0b100
    CALL_IND = 0b101
    RET      = 0b111

class EmberMop(object):
    """ Control signals associated with a macro-op. 

    Members
    =======
    fmt: 
        RISC-V encoding format
    dst:
        Destination operand type[s]
    src1:
        First source operand type
    src2:
        Second source operand type
    alu_op:
        ALU operation
    brn_op:
        Branch operation
    jmp_op:
        Jump operation
    sys_op:
        System operation
    ld_op:
        Load operation
    st_op:
        Store operation
    """
    layout = StructLayout({
        "fmt": RvFormat,
        "dst": DestOperand,
        "src1": SourceOperand,
        "src2": SourceOperand,
        "alu_op": AluOp,
        "brn_op": BrnOp,
        "jmp_op": JmpOp,
        "sys_op": SysOp,
        "ld_op": LoadOp,
        "st_op": StoreOp,
    })
    def __init__(self, fmt: RvFormat, 
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
            "fmt": fmt,
            "dst": dst.value,
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
    "AUIPC":  EmberMop(RvFormat.U, alu_op=AluOp.ADD,  src1=SourceOperand.PC,  src2=SourceOperand.IMM,  dst=DestOperand.RD,),
    "LUI":    EmberMop(RvFormat.U, alu_op=AluOp.ADD,  src1=SourceOperand.IMM, src2=SourceOperand.ZERO, dst=DestOperand.RD,),
    "JAL":    EmberMop(RvFormat.J, jmp_op=JmpOp.JAL,  src1=SourceOperand.PC,  src2=SourceOperand.IMM,  dst=(DestOperand.RD|DestOperand.PC)),
    "JALR":   EmberMop(RvFormat.I, jmp_op=JmpOp.JALR, src1=SourceOperand.RS1, src2=SourceOperand.IMM,  dst=(DestOperand.RD|DestOperand.PC)),

    "BEQ":    EmberMop(RvFormat.B, brn_op=BrnOp.EQ,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.PC,),
    "BNE":    EmberMop(RvFormat.B, brn_op=BrnOp.NE,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.PC,),
    "BLT":    EmberMop(RvFormat.B, brn_op=BrnOp.LT,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.PC,),
    "BGE":    EmberMop(RvFormat.B, brn_op=BrnOp.GE,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.PC,),
    "BLTU":   EmberMop(RvFormat.B, brn_op=BrnOp.LTU, src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.PC,),
    "BGEU":   EmberMop(RvFormat.B, brn_op=BrnOp.GEU, src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.PC,),

    "LB":     EmberMop(RvFormat.I, ld_op=LoadOp.B,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "LH":     EmberMop(RvFormat.I, ld_op=LoadOp.H,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "LW":     EmberMop(RvFormat.I, ld_op=LoadOp.W,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "LBU":    EmberMop(RvFormat.I, ld_op=LoadOp.BU, src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "LHU":    EmberMop(RvFormat.I, ld_op=LoadOp.HU, src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),

    "SB":     EmberMop(RvFormat.S, st_op=StoreOp.B, src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.MEM,),
    "SH":     EmberMop(RvFormat.S, st_op=StoreOp.H, src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.MEM,),
    "SW":     EmberMop(RvFormat.S, st_op=StoreOp.W, src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.MEM,),

    "ADDI":   EmberMop(RvFormat.I, alu_op=AluOp.ADD,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "SLTI":   EmberMop(RvFormat.I, alu_op=AluOp.SLT,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "SLTIU":  EmberMop(RvFormat.I, alu_op=AluOp.SLTU, src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "XORI":   EmberMop(RvFormat.I, alu_op=AluOp.XOR,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "ORI":    EmberMop(RvFormat.I, alu_op=AluOp.OR,   src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "ANDI":   EmberMop(RvFormat.I, alu_op=AluOp.AND,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "SLLI":   EmberMop(RvFormat.I, alu_op=AluOp.SLL,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "SRLI":   EmberMop(RvFormat.I, alu_op=AluOp.SRL,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),
    "SRAI":   EmberMop(RvFormat.I, alu_op=AluOp.SRA,  src1=SourceOperand.RS1, src2=SourceOperand.IMM, dst=DestOperand.RD,),

    "ADD":    EmberMop(RvFormat.R, alu_op=AluOp.ADD,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "SUB":    EmberMop(RvFormat.R, alu_op=AluOp.SUB,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "SLL":    EmberMop(RvFormat.R, alu_op=AluOp.SLL,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "SLT":    EmberMop(RvFormat.R, alu_op=AluOp.SLT,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "SLTU":   EmberMop(RvFormat.R, alu_op=AluOp.SLTU, src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "XOR":    EmberMop(RvFormat.R, alu_op=AluOp.XOR,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "SRL":    EmberMop(RvFormat.R, alu_op=AluOp.SRL,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "SRA":    EmberMop(RvFormat.R, alu_op=AluOp.SRA,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "OR":     EmberMop(RvFormat.R, alu_op=AluOp.OR,   src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),
    "AND":    EmberMop(RvFormat.R, alu_op=AluOp.AND,  src1=SourceOperand.RS1, src2=SourceOperand.RS2, dst=DestOperand.RD,),

    "FENCE":  EmberMop(RvFormat.I, sys_op=SysOp.FENCE),
    "ECALL":  EmberMop(RvFormat.I, sys_op=SysOp.ECALL),
    "EBREAK": EmberMop(RvFormat.I, sys_op=SysOp.EBREAK),
})




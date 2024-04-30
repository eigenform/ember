
from amaranth import *
from amaranth.lib.data import *
from amaranth.lib.enum import Enum

class RvFormat(Enum, shape=unsigned(3)):
    R = 0b000
    I = 0b001
    S = 0b010
    B = 0b011
    U = 0b100
    J = 0b101

class RvOpcode(Enum, shape=unsigned(5)):
    LOAD      = 0b00000
    LOADFP    = 0b00001
    CUSTOM0   = 0b00010
    MISCMEM   = 0b00011
    OPIMM     = 0b00100
    AUIPC     = 0b00101
    OPIMM32   = 0b00110
    RESERVED0 = 0b00111

    STORE     = 0b01000
    STOREFP   = 0b01001
    CUSTOM1   = 0b01010
    AMO       = 0b01011
    OP        = 0b01100
    LUI       = 0b01101
    OP32      = 0b01110
    RESERVED1 = 0b01111

    MADD      = 0b10000
    MSUB      = 0b10001
    NMSUB     = 0b10010
    NMADD     = 0b10011
    OPFP      = 0b10100
    RESERVED2 = 0b10101
    CUSTOM2   = 0b10110
    RESERVED3 = 0b10111

    BRANCH    = 0b11000
    JALR      = 0b11001
    RESERVED4 = 0b11010
    JAL       = 0b11011
    SYSTEM    = 0b11100
    RESERVED5 = 0b11101
    CUSTOM3   = 0b11110
    RESERVED6 = 0b11111

#class RV32Instr(Struct):
#    bits: unsigned(32)
#    def op(self):  return self.bits[2:7]
#    def rd(self):  return self.bits[7:12]
#    def f3(self):  return self.bits[12:15]
#    def rs1(self): return self.bits[15:20]
#    def rs2(self): return self.bits[20:25]
#    def f7(self):  return self.bits[25:32]
#    def f12(self): return self.bits[20:32]
#
#    def i_simm12(self): 
#        return Cat(self.bits[20:], Repl(self.bits[-1], 20))
#    def u_imm20(self):
#        return Cat(C(0,12), self.bits[12:])
#    def s_simm12(self):
#        return Cat(self.bits[7:12], self.bits[25:], Repl(self.bits[-1], 20))
#    def b_simm12(self):
#        return Cat(C(0,1), self.bits[8:12], self.bits[25:31], self.bits[7],
#                   Repl(self.bits[-1], 20))
#    def j_simm20(self):
#        return Cat(C(0,1), self.bits[21:31], self.bits[20], self.bits[12:20],
#                   Repl(self.bits[-1], 12))



class RvEncodingR(StructLayout):
    def __init__(self):
        super().__init__({
            "opcode": RvOpcode,
            "rd": unsigned(5),
            "funct3": unsigned(3),
            "rs1": unsigned(5),
            "rs2": unsigned(5),
            "funct7": unsigned(7),
        })

class RvEncodingI(StructLayout):
    def __init__(self):
        super().__init__({
            "opcode": RvOpcode,
            "rd": unsigned(5),
            "funct3": unsigned(3),
            "rs1": unsigned(5),
            "imm12": unsigned(12),
        })

class RvEncodingS(StructLayout):
    def __init__(self):
        super().__init__({
            "opcode": RvOpcode,
            "imm12_0_4": unsigned(5),
            "funct3": unsigned(3),
            "rs1": unsigned(5),
            "rs2": unsigned(5),
            "imm12_5_11": unsigned(7),
        })

class RvEncodingB(StructLayout):
    def __init__(self):
        super().__init__({
            "opcode": RvOpcode,
            "imm12_11": unsigned(1),
            "imm12_1_4": unsigned(4),
            "funct3": unsigned(3),
            "rs1": unsigned(5),
            "rs2": unsigned(5),
            "imm12_5_10": unsigned(6),
            "imm12_12": unsigned(1),
        })

class RvEncodingU(StructLayout):
    def __init__(self):
        super().__init__({
            "opcode": RvOpcode,
            "rd": unsigned(5),
            "imm20_12_31": unsigned(20),
        })

class RvEncodingJ(StructLayout):
    def __init__(self):
        super().__init__({
            "opcode": RvOpcode,
            "rd": unsigned(5),
            "imm20_12_19": unsigned(8),
            "imm20_11": unsigned(1),
            "imm20_1_10": unsigned(10),
            "imm20_20": unsigned(1),
        })

class F3Op(Enum, shape=unsigned(3)):
    ADD  = 0b000
    SUB  = 0b000
    SLL  = 0b001
    SLT  = 0b010
    SLTU = 0b011
    XOR  = 0b100
    SR   = 0b101
    OR   = 0b110
    AND  = 0b111

class F3OpImm(Enum, shape=unsigned(3)):
    ADDI  = 0b000
    SLLI  = 0b001
    SLTI  = 0b010
    SLTIU = 0b011
    XORI  = 0b100
    SRLI  = 0b101
    SRAI  = 0b101
    ORI   = 0b110
    ANDI  = 0b111

class F3Branch(Enum, shape=unsigned(3)):
    BEQ  = 0b000
    BNE  = 0b001
    BLT  = 0b100
    BGE  = 0b101
    BLTU = 0b110
    BGEU = 0b111

class F3Ldst(Enum, shape=unsigned(3)):
    B  = 0b000
    H  = 0b001
    W  = 0b010
    BU = 0b100
    HU = 0b101

class F3Zicsr(Enum, shape=unsigned(3)):
    CSRRW  = 0b001
    CSRRS  = 0b010
    CSRRC  = 0b011
    CSRRWI = 0b101
    CSRRSI = 0b110
    CSRRCI = 0b111

class F3Mul(Enum, shape=unsigned(3)):
    MUL    = 0b000
    MULH   = 0b001
    MULHSU = 0b010
    MULHU  = 0b011
    DIV    = 0b100
    DIVU   = 0b101
    REM    = 0b110
    REMU   = 0b111

class RvInst(object):
    def __init__(self, name, fmt: RvFormat, opcode: RvOpcode, 
                 f3=None, f7=None, f12=None, rd=None, rs1=None):
        self.name = name
        self.fmt = fmt
        self.opcode = opcode
        self.rd = rd
        self.rs1 = rs1
        self.f3 = f3
        self.f7 = f7
        self.f12 = f12

RV32I_BASE_SET = {
    "AUIPC": RvInst("AUIPC", RvFormat.U, RvOpcode.AUIPC),
    "LUI":  RvInst("LUI", RvFormat.U, RvOpcode.LUI),

    "JAL":  RvInst("JAL", RvFormat.J, RvOpcode.JAL),
    "JALR": RvInst("JALR", RvFormat.I, RvOpcode.JALR, f3=0b000),

    "BEQ":  RvInst("BEQ", RvFormat.B, RvOpcode.BRANCH, f3=F3Branch.BEQ),
    "BNE":  RvInst("BNE", RvFormat.B, RvOpcode.BRANCH, f3=F3Branch.BNE),
    "BLT":  RvInst("BLT", RvFormat.B, RvOpcode.BRANCH, f3=F3Branch.BLT),
    "BGE":  RvInst("BGE", RvFormat.B, RvOpcode.BRANCH, f3=F3Branch.BGE),
    "BLTU": RvInst("BLTU", RvFormat.B, RvOpcode.BRANCH, f3=F3Branch.BLTU),
    "BGEU": RvInst("BGEU", RvFormat.B, RvOpcode.BRANCH, f3=F3Branch.BGEU),

    "LB":   RvInst("LB", RvFormat.I, RvOpcode.LOAD, f3=F3Ldst.B),
    "LH":   RvInst("LH", RvFormat.I, RvOpcode.LOAD, f3=F3Ldst.H),
    "LW":   RvInst("LW", RvFormat.I, RvOpcode.LOAD, f3=F3Ldst.W),
    "LBU":  RvInst("LBU", RvFormat.I, RvOpcode.LOAD, f3=F3Ldst.BU),
    "LHU":  RvInst("LHU", RvFormat.I, RvOpcode.LOAD, f3=F3Ldst.HU),

    "SB":   RvInst("SB", RvFormat.S, RvOpcode.STORE, f3=F3Ldst.B),
    "SH":   RvInst("SH", RvFormat.S, RvOpcode.STORE, f3=F3Ldst.H),
    "SW":   RvInst("SW", RvFormat.S, RvOpcode.STORE, f3=F3Ldst.W),

    "ADDI":  RvInst("ADDI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.ADDI),
    "SLTI":  RvInst("SLTI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.SLTI),
    "SLTIU": RvInst("SLTIU", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.SLTIU),
    "XORI":  RvInst("XORI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.XORI),
    "ORI":   RvInst("ORI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.ORI),
    "ANDI":  RvInst("ANDI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.ANDI),

    "SLLI":  RvInst("SLLI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.SLLI, f7=0b0000000),
    "SRLI":  RvInst("SRLI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.SRLI, f7=0b0000000),
    "SRAI":  RvInst("SRAI", RvFormat.I, RvOpcode.OPIMM, f3=F3OpImm.SRAI, f7=0b0100000),

    "ADD":  RvInst("ADD", RvFormat.R, RvOpcode.OP, f3=F3Op.ADD, f7=0b0000000),
    "SUB":  RvInst("SUB", RvFormat.R, RvOpcode.OP, f3=F3Op.SUB, f7=0b0100000),
    "SLL":  RvInst("SLL", RvFormat.R, RvOpcode.OP, f3=F3Op.SLL, f7=0b0000000),
    "SLT":  RvInst("SLT", RvFormat.R, RvOpcode.OP, f3=F3Op.SLT, f7=0b0000000),
    "SLTU": RvInst("SLTU", RvFormat.R, RvOpcode.OP, f3=F3Op.SLTU, f7=0b0000000),
    "XOR":  RvInst("XOR", RvFormat.R, RvOpcode.OP, f3=F3Op.XOR, f7=0b0000000),
    "SRL":  RvInst("SRL", RvFormat.R, RvOpcode.OP, f3=F3Op.SR, f7=0b0000000),
    "SRA":  RvInst("SRA", RvFormat.R, RvOpcode.OP, f3=F3Op.SR, f7=0b0100000),
    "OR":   RvInst("OR", RvFormat.R, RvOpcode.OP, f3=F3Op.OR, f7=0b0000000),
    "AND":  RvInst("AND", RvFormat.R, RvOpcode.OP, f3=F3Op.AND, f7=0b0000000),

    "FENCE":  RvInst("FENCE", RvFormat.I, RvOpcode.MISCMEM, f3=0b000),
    "ECALL":  RvInst("ECALL", RvFormat.I, RvOpcode.SYSTEM, 
                     f3=0b000, rd=0b00000, rs1=0b00000, f12=0b0000_0000_0000),
    "EBREAK": RvInst("EBREAK", RvFormat.I, RvOpcode.SYSTEM, 
                      f3=0b000, rd=0b00000, rs1=0b00000, f12=0b0000_0000_0001),
}

ZIFENCEI_SET = {
    "FENCE.I": RvInst("FENCE.I", RvFormat.I, RvOpcode.MISCMEM, f3=0b001)
}

ZICSR_SET = {
    "CSRRW":  RvInst("CSRRW", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRW),
    "CSRRS":  RvInst("CSRRS", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRS),
    "CSRRC":  RvInst("CSRRC", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRC),
    "CSRRWI": RvInst("CSRRWI", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRWI),
    "CSRRSI": RvInst("CSRRSI", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRSI),
    "CSRRCI": RvInst("CSRRCI", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRCI),
}

RV32M_SET = {
    "MUL":    RvInst("MUL", RvFormat.R, RvOpcode.OP, f3=F3Mul.MUL, f7=0b0000001),
    "MULH":   RvInst("MULH", RvFormat.R, RvOpcode.OP, f3=F3Mul.MULH, f7=0b0000001),
    "MULHSU": RvInst("MULHSU", RvFormat.R, RvOpcode.OP, f3=F3Mul.MULHSU, f7=0b0000001),
    "MULHU":  RvInst("MULHU", RvFormat.R, RvOpcode.OP, f3=F3Mul.MULHU, f7=0b0000001),
    "DIV":    RvInst("DIV", RvFormat.R, RvOpcode.OP, f3=F3Mul.DIV, f7=0b0000001),
    "DIVU":   RvInst("DIVU", RvFormat.R, RvOpcode.OP, f3=F3Mul.DIVU, f7=0b0000001),
    "REM":    RvInst("REM", RvFormat.R, RvOpcode.OP, f3=F3Mul.REM, f7=0b0000001),
    "REMU":   RvInst("REMU", RvFormat.R, RvOpcode.OP, f3=F3Mul.REMU, f7=0b0000001),
}




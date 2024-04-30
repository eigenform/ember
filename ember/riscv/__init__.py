
from amaranth.lib.enum import *
from .encoding import *

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


RvMacroOp = Enum("RvMacroOp", 
    [ op for op in RV32I_BASE_SET ]
)



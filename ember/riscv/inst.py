from amaranth.lib.enum import *
from amaranth.utils import exact_log2, ceil_log2
from .encoding import *

class RvInstMatch(object):
    """ Container for the string representation of a bitmask used to 
    uniquely identify a RISC-V instruction.
    """
    def __init__(self):
        self.data = [ '-' for _ in range(32) ]

    def __str__(self):
        """ Return the string representation of the bitmask. """
        return "".join(x for x in reversed(self.data))

    def as_string(self): 
        """ Return the string representation of the bitmask. """
        return str(self)

    def num_effective_bits(self):
        """ Return the number of effective bits in the mask. """
        return 32 - self.data.count("-")

    def add_match_value(self, start: int, size: int, val: int):
        """ Define some bits in the mask at the provided location. """
        s = "{:0{width}b}".format(val, width=size)
        s_rev = list(reversed(s))
        assert(len(s) == size)
        for i in range(size):
            self.data[start+i] = s_rev[i]

class RvInst(object):
    """ Definition of a RISC-V instruction. """
    def __init__(self, name, fmt: RvFormat, 
                 opcode: RvOpcode, 
                 f3=None, f7=None, f12=None, rd=None, rs1=None):

        if f7 != None and f12 != None:
            raise ValueError("wuhhhhhhhh")

        self.name = name
        self.fmt = fmt
        self.constraints = {}
        self.constraints['opcode_low'] = 0b11
        self.constraints['opcode'] = opcode.value
        if rd != None: 
            self.constraints['rd'] = rd
        if rs1 != None: 
            self.constraints['rs1'] = rs1
        if f3 != None: 
            if isinstance(f3, int):
                self.constraints['f3'] = f3
            elif isinstance(f3, Enum):
                self.constraints['f3'] = f3.value
        if f7 != None: 
            self.constraints['f7'] = f7
        if f12 != None: 
            self.constraints['f12'] = f12

    def specificity(self):
        return self.match().num_effective_bits()

    def match(self):
        """ Return the :class:`RvInstMatch` associated with this instruction. 
        """
        res = RvInstMatch()
        for name, constraint in self.constraints.items():
            match name:
                case "opcode_low": res.add_match_value(0, 2, constraint)
                case "opcode": res.add_match_value(2, 5, constraint)
                case "rd": res.add_match_value(7, 5, constraint)
                case "rs1": res.add_match_value(15, 5, constraint)
                case "f3": res.add_match_value(12, 3, constraint)
                case "f7": res.add_match_value(25, 7, constraint)
                case "f12": res.add_match_value(20, 12, constraint)
                case _: raise ValueError(f"unknown field '{name}'")
        return res

class RvInstGroup(object):
    """ A group of supported RISC-V instructions. """
    def __init__(self, name="", members={}):
        self.name = name
        self.members = members

    def add_group(self, other):
        """ Append another group to this group. """
        assert isinstance(other, RvInstGroup)
        self.members.update(other.members)

    def enum_type(self, enum_name="RvInstId"):
        """ Construct an Enum type containing all instructions in this group. 
        """
        return Enum(enum_name, [ op for op in self.members ],start=0)

    def members_by_specificity(self):
        return sorted(self.members.items(), key=lambda x: x[1].specificity())

    def id_shape(self):
        return unsigned(ceil_log2((len(self.members))))
    def id_shape_onehot(self):
        return unsigned(len(self.members))

RV32I_PSEUDO = RvInstGroup(members={
    "NOP": RvInst("NOP", RvFormat.I, RvOpcode.OPIMM, 
                  f3=F3OpImm.ADDI, rd=0,rs1=0,f12=0),
})


RV32I_BASE_SET = RvInstGroup(members={
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
})

ZIFENCEI_SET = RvInstGroup(members={
    "FENCE.I": RvInst("FENCE.I", RvFormat.I, RvOpcode.MISCMEM, f3=0b001)
})

ZICSR_SET = RvInstGroup(members={
    "CSRRW":  RvInst("CSRRW", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRW),
    "CSRRS":  RvInst("CSRRS", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRS),
    "CSRRC":  RvInst("CSRRC", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRC),
    "CSRRWI": RvInst("CSRRWI", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRWI),
    "CSRRSI": RvInst("CSRRSI", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRSI),
    "CSRRCI": RvInst("CSRRCI", RvFormat.I, RvOpcode.SYSTEM, f3=F3Zicsr.CSRRCI),
})

RV32M_SET = RvInstGroup(members={
    "MUL":    RvInst("MUL", RvFormat.R, RvOpcode.OP, f3=F3Mul.MUL, f7=0b0000001),
    "MULH":   RvInst("MULH", RvFormat.R, RvOpcode.OP, f3=F3Mul.MULH, f7=0b0000001),
    "MULHSU": RvInst("MULHSU", RvFormat.R, RvOpcode.OP, f3=F3Mul.MULHSU, f7=0b0000001),
    "MULHU":  RvInst("MULHU", RvFormat.R, RvOpcode.OP, f3=F3Mul.MULHU, f7=0b0000001),
    "DIV":    RvInst("DIV", RvFormat.R, RvOpcode.OP, f3=F3Mul.DIV, f7=0b0000001),
    "DIVU":   RvInst("DIVU", RvFormat.R, RvOpcode.OP, f3=F3Mul.DIVU, f7=0b0000001),
    "REM":    RvInst("REM", RvFormat.R, RvOpcode.OP, f3=F3Mul.REM, f7=0b0000001),
    "REMU":   RvInst("REMU", RvFormat.R, RvOpcode.OP, f3=F3Mul.REMU, f7=0b0000001),
})




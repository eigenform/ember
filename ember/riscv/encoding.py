from amaranth import *
from amaranth.lib.data import *
from amaranth.lib.enum import Enum

class RvFormat(Enum, shape=unsigned(3)):
    """ The format for a RISC-V instruction encoding. """
    R = 0b000
    I = 0b001
    S = 0b010
    B = 0b011
    U = 0b100
    J = 0b101

class RvOpcode(Enum, shape=unsigned(5)):
    """ A RISC-V opcode. """
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

class F3Op(Enum, shape=unsigned(3)):
    """ Funct3 values for the OP opcode """
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
    """ Funct3 values for the OPIMM opcode """
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
    """ Funct3 values for the BRANCH opcode """
    BEQ  = 0b000
    BNE  = 0b001
    BLT  = 0b100
    BGE  = 0b101
    BLTU = 0b110
    BGEU = 0b111

class F3Ldst(Enum, shape=unsigned(3)):
    """ Funct3 values for the LOAD/STORE opcode """
    B  = 0b000
    H  = 0b001
    W  = 0b010
    BU = 0b100
    HU = 0b101

class F3Zicsr(Enum, shape=unsigned(3)):
    """ Funct3 values for Zicsr instructions """
    CSRRW  = 0b001
    CSRRS  = 0b010
    CSRRC  = 0b011
    CSRRWI = 0b101
    CSRRSI = 0b110
    CSRRCI = 0b111

class F3Mul(Enum, shape=unsigned(3)):
    """ Funct3 values for RV32M instructions """
    MUL    = 0b000
    MULH   = 0b001
    MULHSU = 0b010
    MULHU  = 0b011
    DIV    = 0b100
    DIVU   = 0b101
    REM    = 0b110
    REMU   = 0b111


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


class RvEncoding(FlexibleLayout):
    """ Layout associated with a RISC-V instruction encoding. 
    """
    def __init__(self):
        super().__init__(32, {
            "opcode_low": Field(unsigned(2), 0),
            "opcode":     Field(unsigned(5), 2),
            "rd":         Field(unsigned(5), 7),
            "f3":         Field(unsigned(3), 12),
            "rs1":        Field(unsigned(5), 15),
            "rs2":        Field(unsigned(5), 20),
            "f12":        Field(unsigned(12),20),
            "f7":         Field(unsigned(7), 25),

            # I-type fields
            "i_imm12":      Field(unsigned(12), 20),

            # S-type fields
            "s_imm12_0_4":  Field(unsigned(5), 7),
            "s_imm12_5_11": Field(unsigned(7), 25),

            # B-type fields
            "b_imm12_11":   Field(unsigned(1), 7),
            "b_imm12_1_4":  Field(unsigned(4), 8),
            "b_imm12_5_10": Field(unsigned(6), 25),
            "b_imm12_12":   Field(unsigned(1), 31),

            # U-type fields
            "u_imm20_12_31": Field(unsigned(20), 12),

            # J-type fields
            "j_imm20_12_19": Field(unsigned(8), 12),
            "j_imm20_11":    Field(unsigned(1), 20),
            "j_imm20_1_10":  Field(unsigned(10), 21),
            "j_imm20_20":    Field(unsigned(1), 31),

            # Useful aliases
            "shamt": Field(unsigned(5), 20),
            "csr":   Field(unsigned(12),20),
            "sign":  Field(unsigned(1), 31),
            "raw":   Field(unsigned(32), 0),
        })

class RvEncodingImmediateView(View):
    def __init__(self, target):
        super().__init__(RvEncoding(), target)

    def get_i_imm12(self):
        """ Return the raw 12-bit I-type immediate """
        return self.i_imm12

    def get_s_imm12(self):
        """ Return the raw 12-bit S-type immediate """
        return Cat(self.s_imm12_0_4, self.s_imm12_5_11)

    def get_b_imm12(self):
        """ Return the raw 12-bit B-type immediate """
        return Cat(C(0,1), self.b_imm12_1_4, self.b_imm12_5_10, 
                   self.b_imm12_11, self.b_imm12_12)

    def get_u_imm20(self):
        """ Return the raw 20-bit U-type immediate """
        return self.u_imm20_12_31

    def get_j_imm20(self):
        """ Return the raw 20-bit J-type immediate """
        return Cat(C(0,1), self.j_imm20_1_10, self.j_imm20_11,
                   self.j_imm20_12_19, self.j_imm20_20)



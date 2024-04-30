from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2

# Table of LFSR taps yielding the maximal-length period (up to 64 bits). 
# See https://docs.amd.com/v/u/en-US/xapp052
TAPS = { 
    3:  [3, 2],
    4:  [4, 3],
    5:  [5, 3],
    6:  [6, 5],
    7:  [7, 6],
    8:  [8, 6, 5, 4],
    9:  [9, 5],
    10: [10, 7],
    11: [11, 9],
    12: [12, 6, 4, 1],
    13: [13, 4, 3, 1],
    14: [14, 5, 3, 1],
    15: [15, 14],
    16: [16, 15, 13, 4],
    17: [17, 14],
    18: [18, 11],
    19: [19, 6, 2, 1],
    20: [20, 17],
    21: [21, 19],
    22: [22, 21],
    23: [23, 18],
    24: [24, 23, 22, 17],
    25: [25, 22],
    26: [26, 6, 2, 1],
    27: [27, 5, 2, 1],
    28: [28, 25],
    29: [29, 27],
    30: [30, 6, 4, 1],
    31: [31, 28],
    32: [32, 22, 2, 1],
    33: [33, 20],
    34: [34, 27, 2, 1],
    35: [35, 33],
    36: [36, 25],
    37: [37, 5, 4, 3, 2, 1],
    38: [38, 6, 5, 1],
    39: [39, 35],
    40: [40, 38, 21, 19],
    41: [41, 38],
    42: [42, 41, 20, 19],
    43: [43, 42, 38, 37],
    44: [44, 43, 18, 17],
    45: [45, 44, 42, 41],
    46: [46, 45, 26, 25],
    47: [47, 42],
    48: [48, 47, 21, 20],
    49: [49, 40],
    50: [50, 49, 24, 23],
    51: [51, 50, 36, 35],
    52: [52, 49],
    53: [53, 52, 38, 37],
    54: [54, 53, 18, 17],
    55: [55, 31],
    56: [56, 55, 35, 34],
    57: [57, 50],
    58: [58, 39],
    59: [59, 58, 38, 37],
    60: [60, 59],
    61: [61, 60, 46, 45],
    62: [62, 61, 6, 5],
    63: [63, 62],
    64: [64, 63, 61, 60],
}

class LFSR(Elaboratable):
    """ Linear Feedback Shift Register

    This is plagarized from GlasgowEmbedded/glasgow, but we're generating 
    taps that give us the maximal period length for the requested width. 
    The table only describes registers from 3-bit to 64-bit. 
    """
    def __init__(self, degree, reset=1):
        assert reset != 0
        assert degree >= 3 and degree <= 64
        self.reset = reset
        self.degree = degree
        self.taps = TAPS[degree]
        self.value = Signal(degree, init=reset)

    def elaborate(self, platform):
        m = Module()
        feedback = 0
        for tap in self.taps:
            feedback ^= (self.value >> (tap - 1)) & 1
        m.d.sync += self.value.eq((self.value << 1) | feedback)
        return m

    def generate(self):
        """ Generate every distinct value the LFSR will take. """
        value = self.reset
        mask  = (1 << self.degree) - 1
        while True:
            yield value
            feedback = 0
            for tap in self.taps:
                feedback ^= (value >> (tap - 1)) & 1
            value = ((value << 1) & mask) | feedback
            if value == self.reset:
                break

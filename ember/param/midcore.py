
from ember.param.riscv import *

class DecodeParams(object):
    """ Instruction decode parameters.

    Depends on an instance of :class:`RiscvParams`.

    Parameters
    ==========
    width:
        Number of instructions decoded per cycle

    """
    def __init__(self, rv: RiscvParams, width: int):
        self.width = width



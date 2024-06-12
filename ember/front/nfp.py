from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum

from ember.common import *
from ember.common.pipeline import *
from ember.common.coding import ChainedPriorityEncoder
from ember.param import *
from ember.front.predecode import *
from ember.uarch.fetch import *

class NFPRequest(Signature):
    """ A request for a next-fetch prediction. 

    Members
    =======
    valid:
        This request is valid.
    pc: 
        The program counter used to make a prediction.

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "pc": Out(p.vaddr),
        })

class NFPResponse(Signature):
    """ A response from the next-fetch predictor. 

    Members
    =======
    valid:
        This response is valid.
    npc:
        Output predicted program counter value from the NFP.
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "npc": Out(p.vaddr),
        })


class NextFetchPredictor(Component):
    """ The next-fetch predictor (or "L0 predictor", "zero-cycle predictor").

    Given a program counter value, [combinationally] predict the next program 
    counter value that will be sent to the FTQ. 

    In general, the logic for this should be something like: 

    1. Combinationally read metadata about the associated fetch block
    2. Go to the offset in the fetch block given by the offset bits in the PC
    3. Find the first predicted-taken control-flow instruction
    4. Invoke the appropriate L0 predictor
    5. If no predicted-taken control-flow instruction is found, fallback to
       predicting the address of the next-sequential fetch block. 

    """

    def __init__(self, param: EmberParams): 
        self.p = param
        sig = Signature({
            "req": In(NFPRequest(param)),
            "resp": Out(NFPResponse(param)),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        fblk_addr = self.req.pc.get_fetch_addr()



        # Predict the next-sequential fetch block address
        m.d.comb += [
            self.resp.valid.eq(self.req.valid),
            self.resp.npc.eq(fblk_addr + 0x20),
        ]

        return m




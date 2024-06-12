from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *

from ember.common import *
from ember.common.queue import *
from ember.param import *
from ember.uarch.fetch import *

class DecodeQueue(Component):
    """ A queue for instructions waiting to move through the mid-core. 

    .. note::
        For now, an entry in the decode queue is an entire fetch block
        (including invalid entries which might come before the requested
        program counter). 

        This means that we're wasting space when the stream of requested 
        program counter values is not naturally aligned to L1I boundaries.

        Instead, we should probably insert only "valid" words from the L1I 
        cacheline into the queue. This implies tracking the boundaries of 
        fetch blocks or the associated FTQ indexes that are moving through 
        the queue. Note that an "efficient" version of that might be totally 
        incompatible with an implementation based on :class:`CreditQueue`. 

    Ports
    =====
    up: 
        Upstream queue interface (with front-end)
    down: 
        Downstream queue interface (with mid-core)

    """
    def __init__(self, param: EmberParams):
        self.p = param
        self.depth = 16
        self.width = 1
        super().__init__(Signature({
            "up":   In(CreditQueueUpstream(self.width, DecodeQueueEntry(param))),
            "down": Out(CreditQueueDownstream(self.width, DecodeQueueEntry(param))),
        }))

    def elaborate(self, platform):
        m = Module()

        q = m.submodules.q = CreditQueue(16, 1, DecodeQueueEntry(self.p))
        connect(m, flipped(self.up), q.up)
        connect(m, q.down, flipped(self.down))

        return m


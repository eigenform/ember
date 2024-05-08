
import functools
import operator
import itertools

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2, exact_log2

def popcount(x: Value) -> Value:
    """ Return the number of ones set in the provided Value. """
    return functools.reduce(operator.add, iter(x))

class PopCount(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.i = Signal(width)
        self.o = Signal(ceil_log2(width))
    def elaborate(self, platform):
        m = Module()
        m.d.comb += [
            self.o.eq(functools.reduce(operator.add, iter(self.i))),
        ]
        return m


def chunks(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))



import functools
import operator
import itertools
from typing import Callable, Iterable
import typing
from math import floor
#from collections.abc import Iterable

from amaranth import tracer

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


def is_log2(x: int):
    return (x != 0 and (x & (x-1) == 0))

def chunks(iterable, size):
    it = iter(iterable)
    item = list(itertools.islice(it, size))
    while item:
        yield item
        item = list(itertools.islice(it, size))

class PriorityMux(Component):
    """ A chain of muxes. 

    Selects the first signal for which the corresponding select bit is high. 

    Ports
    =====
    sel: 
        Input select signals
    val: 
        Input data signals
    output: 
        Output data signal (zero when the 'valid' bit is low)
    valid:
        Output valid (high when any of the select bits are valid)

    """

    def __init__(self, shape: Shape, depth: int):
        """ Create a new PriorityMux.

        Parameters
        ==========
        shape: 
            The shape of the input/output data 
        depth: 
            The number of chained muxes
        """

        self.data_shape = shape
        if isinstance(shape, Layout):
            self.zero_const = Layout.from_bits(shape, 0)
        else:
            self.zero_const = C(0, shape)

        self.depth = depth
        signature = Signature({
            "output": Out(shape),
            "valid": Out(1),
            "sel": In(1).array(depth),
            "val": In(shape).array(depth),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        def mux_reduce(prev: tuple[Signal, Signal], e: tuple[Signal,Signal]):
            result = Mux(e[0], e[1], prev[1])
            return (e[0], result)

        inputs = list(zip(list(self.sel), list(self.val)))
        if self.depth == 1:
            m.d.comb += self.output.eq(self.val[0])
            m.d.comb += self.valid.eq(1)
        else:
            output = functools.reduce(
                #mux_reduce, reversed(inputs), (C(1,1), C(0,self.data_shape))
                mux_reduce, reversed(inputs), (C(1,1), self.zero_const)
            )
            m.d.comb += self.output.eq(output[1])
            m.d.comb += self.valid.eq(Cat(*self.sel).any())

        return m 



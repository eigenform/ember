
import functools
import operator
import itertools
from typing import Callable, Iterable, Optional
import typing
from math import floor
#from collections.abc import Iterable

from amaranth import tracer

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2, exact_log2

def reverse_bits(val: Value):
    """ Reverse all of the bits in the provided 'Value' 

    For example, `0b0101` becomes `0b1010`. 
    """
    rev = [ val[idx] for idx in reversed(range(len(val))) ]
    return Cat(*rev)

def offset2masklut(mask_width: int, off: Value):
    """ Given a bit index 'off', yields a bitmask where all of the bits in 
    the range `[off:mask_width-1]` (inclusive) are set. 
    For example (where `mask_width` is 8):

    - 0 yields `0b1111_1111`
    - 1 yields `0b1111_1110`
    - 2 yields `0b1111_1100`
    - 3 yields `0b1111_1000`
    """
    def fill(x): 
        res = (1 << mask_width)-1
        for v in range(x): res ^= (1<<v)
        return res
    assert len(off) >= exact_log2(mask_width), \
        "{} != {}".format(len(off), exact_log2(mask_width))
    arr = Array([ C(fill(n), mask_width) for n in range(mask_width) ])
    return arr[off]

def limit2masklut(mask_width: int, lim: Value):
    """ Given a bit index 'lim', yields a bitmask where all of the bits in
    the range `[0:lim]` (inclusive) are set. 
    For example (where `mask_width` is 8):

    - 0 yields `0b0000_0001`
    - 1 yields `0b0000_0011`
    - 2 yields `0b0000_0111`
    - 3 yields `0b0000_1111`
    """
    def fill(x): 
        res = 0
        for v in range(x): res |= (1<<v)
        return res
    assert len(lim) >= exact_log2(mask_width), \
        "{} != {}".format(len(lim), exact_log2(mask_width))
    arr = Array([ C(fill(n), mask_width) for n in range(1, mask_width+1) ])
    return arr[lim]




def popcount(x: Value) -> Value:
    """ Return the number of ones set in the provided Value. """
    return functools.reduce(operator.add, iter(x))

class PopCount(Elaboratable):
    def __init__(self, width):
        self.width = width
        self.i = Signal(width)
        self.o = Signal(ceil_log2(width)+1)
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




from amaranth import *
from amaranth.utils import exact_log2, ceil_log2
from ember.common import *

# NOTE: At some point, amaranth.lib.coding will be deprecated. 
# We can keep these around until we want to change them. 

class Encoder(Elaboratable):
    """Encode one-hot to binary.

    If one bit in ``i`` is asserted, ``n`` is low and ``o`` indicates the asserted bit.
    Otherwise, ``n`` is high and ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the input

    Attributes
    ----------
    i : Signal(width), in
        One-hot input.
    o : Signal(range(width)), out
        Encoded natural binary.
    n : Signal, out
        Invalid: either none or multiple input bits are asserted.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(range(width))
        self.n = Signal()

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.i):
            for j in range(self.width):
                with m.Case(1 << j):
                    m.d.comb += self.o.eq(j)
            with m.Default():
                m.d.comb += self.n.eq(1)
        return m


class PriorityEncoder(Elaboratable):
    """Priority encode requests to binary.

    If any bit in ``i`` is asserted, ``n`` is low and ``o`` indicates the least significant
    asserted bit.
    Otherwise, ``n`` is high and ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the input.

    Attributes
    ----------
    i : Signal(width), in
        Input requests.
    o : Signal(range(width)), out
        Encoded natural binary.
    n : Signal, out
        Invalid: no input bits are asserted.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(range(width))
        self.n = Signal()

    def elaborate(self, platform):
        m = Module()
        for j in reversed(range(self.width)):
            with m.If(self.i[j]):
                m.d.comb += self.o.eq(j)
        m.d.comb += self.n.eq(self.i == 0)
        return m


class Decoder(Elaboratable):
    """Decode binary to one-hot.

    If ``n`` is low, only the ``i``-th bit in ``o`` is asserted.
    If ``n`` is high, ``o`` is ``0``.

    Parameters
    ----------
    width : int
        Bit width of the output.

    Attributes
    ----------
    i : Signal(range(width)), in
        Input binary.
    o : Signal(width), out
        Decoded one-hot.
    n : Signal, in
        Invalid, no output bits are to be asserted.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(range(width))
        self.n = Signal()
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        with m.Switch(self.i):
            for j in range(len(self.o)):
                with m.Case(j):
                    m.d.comb += self.o.eq(1 << j)
        with m.If(self.n):
            m.d.comb += self.o.eq(0)
        return m


class PriorityDecoder(Decoder):
    """Decode binary to priority request.

    Identical to :class:`Decoder`.
    """


class GrayEncoder(Elaboratable):
    """Encode binary to Gray code.

    Parameters
    ----------
    width : int
        Bit width.

    Attributes
    ----------
    i : Signal(width), in
        Natural binary input.
    o : Signal(width), out
        Encoded Gray code.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.o.eq(self.i ^ self.i[1:])
        return m


class GrayDecoder(Elaboratable):
    """Decode Gray code to binary.

    Parameters
    ----------
    width : int
        Bit width.

    Attributes
    ----------
    i : Signal(width), in
        Gray code input.
    o : Signal(width), out
        Decoded natural binary.
    """
    def __init__(self, width):
        self.width = width

        self.i = Signal(width)
        self.o = Signal(width)

    def elaborate(self, platform):
        m = Module()
        rhs = Const(0)
        for i in reversed(range(self.width)):
            rhs = rhs ^ self.i[i]
            m.d.comb += self.o[i].eq(rhs)
        return m


class EmberPriorityEncoder(Component):
    """ A priority encoder.

    Ports
    =====
    i:
        Input bits (one-hot)
    mask:
        Output bits (one-hot)
    o:
        Output index (encoded)
    valid:
        High when at least one bit is valid in in the input
    """

    class PriorityEncoderLayout(StructLayout):
        def __init__(self, width: int):
            super().__init__({
                "mask":  unsigned(width),
                "index": unsigned(ceil_log2(width)),
            })

    def __init__(self, width: int):
        """ Create a new priority encoder. 

        Parameters
        ==========
        width: 
            The bit-width of the input value
        """
        assert width != 0
        self.width = width
        super().__init__(Signature({
            "i": In(width),
            "o": Out(ceil_log2(width)),
            "mask": Out(width),
            "valid": Out(1),
        }))

    def elaborate(self, platform):
        m = Module()

        if self.width == 1:
            m.d.comb += self.o.eq(0)
            m.d.comb += self.valid.eq(self.i)
        else:
            table = [
                { "mask": C(1<<idx, self.width), 
                  "index": C(idx, ceil_log2(self.width))
                } for idx in range(self.width)
            ]
            values = [
                C(table[idx], self.PriorityEncoderLayout(self.width))
                for idx in range(self.width)
            ]
            pm = m.submodules.pm = \
                PriorityMux(self.PriorityEncoderLayout(self.width), self.width)
            m.d.comb += [
                pm.val[idx].eq(values[idx]) for idx in range(self.width)
            ]
            m.d.comb += [
                pm.sel[idx].eq(self.i[idx]) for idx in range(self.width)
            ]
            m.d.comb += [
                self.o.eq(pm.output.index),
                self.mask.eq(pm.output.mask),
                self.valid.eq(pm.valid),
            ]

        return m

class ChainedPriorityEncoder(Component):
    def __init__(self, width: int, depth: int):
        assert depth >= 2, "Use EmberPriorityEncoder for cases where depth=1"
        self.depth = depth
        self.width = width
        sig = Signature({
            "i": In(width),
            "o": Out(ceil_log2(width)).array(depth),
            "mask": Out(width).array(depth),
            "valid": Out(1).array(depth),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        encs = [ EmberPriorityEncoder(self.width) for _ in range(self.depth) ]

        mask_input = [ Signal(self.width) for _ in range(self.depth) ]
        for idx in range(self.depth):
            m.submodules[f"enc{idx}"] = encs[idx]

        m.d.comb += encs[0].i.eq(self.i)
        m.d.comb += mask_input[0].eq(self.i & ~encs[0].mask)

        for idx in range(1, self.depth):
            m.d.comb += encs[idx].i.eq(mask_input[idx-1])
            m.d.comb += mask_input[idx].eq(mask_input[idx-1] & ~encs[idx].mask)

        for idx in range(self.depth):
            m.d.comb += self.mask[idx].eq(encs[idx].mask)
            m.d.comb += self.o[idx].eq(encs[idx].o)
            m.d.comb += self.valid[idx].eq(encs[idx].valid)

        return m





from amaranth import *
from amaranth.lib.data import StructLayout, ArrayLayout
from amaranth.lib.enum import Enum
import amaranth.lib.memory
from amaranth.utils import exact_log2

from ember.common import *
from ember.param import *
from ember.front.l1i import *
from ember.front.itlb import *
from ember.uarch.mop import *

class RapRequest(Signature):
    def __init__(self, num_entries: int):
        super().__init__({
            "valid": Out(1),
            "idx": Out(exact_log2(num_entries))
        })
class RapWriteRequest(Signature):
    def __init__(self, num_entries: int):
        super().__init__({
            "valid": Out(1),
            "idx": Out(exact_log2(num_entries)),
            "addr": Out(32),
        })
class RapResponse(Signature):
    def __init__(self, num_entries: int):
        super().__init__({
            "valid": Out(1),
            "idx": Out(exact_log2(num_entries)),
            "addr": Out(32),
        })

class RapPushPort(Signature):
    class Request(Signature):
        """ A request to push an address onto the RAP stack. """
        def __init__(self, num_entries: int):
            super().__init__({
                # This request is valid
                "valid": Out(1),
                # Address to-be-written to the stack
                "addr": Out(32),
            })
    class Response(Signature):
        """ Response to a RAP push request. """
        def __init__(self, num_entries: int):
            super().__init__({
                # This response is valid
                "valid": Out(1),
                # The index of the allocated entry
                "idx": Out(exact_log2(num_entries)),
                # Request caused an overflow condition
                "overflow": Out(1),
            })
    def __init__(self, num_entries: int):
        super().__init__({
            "req": Out(RapPushPort.Request(num_entries)),
            "resp": Out(RapPushPort.Response(num_entries)),
        })

class RapPopPort(Signature):
    class Request(Signature):
        """ A request to pop an address off the RAP stack. """
        def __init__(self, num_entries: int):
            super().__init__({
                # This request is valid
                "valid": Out(1),
                # Index of the entry to-be-read from the stack
                "idx": Out(exact_log2(num_entries)),
            })
    class Response(Signature):
        """ Response to a RAP pop request. """
        def __init__(self, num_entries: int):
            super().__init__({
                # This response is valid
                "valid": Out(1),
                # Index of the entry that was popped off the stack
                "idx": Out(exact_log2(num_entries)),
                # The address that was popped off the stack
                "addr": Out(32),
                # Request caused an underflow condition
                "underflow": Out(1),
            })
    def __init__(self, num_entries: int):
        super().__init__({
            "req":  Out(RapPopPort.Request(num_entries)),
            "resp": In(RapPopPort.Response(num_entries)),
        })




class ReturnAddressPredictor(Component):
    """ A memory device used to track predicted return addresses. 

    .. warning::
        At the moment, this is a simple memory device that does not accomodate 
        overflow/underflow conditions, and we assume that other logic in 
        the pipeline is responsible for interacting with the RAP in a way 
        that actually implements a stack.

    """
    def __init__(self, num_entries: int):
        self.num_entries = num_entries
        signature = Signature({
            "write_req": In(RapWriteRequest(num_entries)),
            "req": In(RapRequest(num_entries)),
            "resp": Out(RapResponse(num_entries)),

            "push": In(RapPushPort(num_entries)),
            "pop": In(RapPushPort(num_entries)),
            "head": Out(32),
        })
        super().__init__(signature)
    def elaborate(self, platform):
        m = Module()
        mem = m.submodules.mem = memory.Memory(
            shape=unsigned(32),
            depth=self.num_entries,
            init=[],
        )

        r_ptr = Signal(exact_log2(self.num_entries))

        rp = mem.read_port(domain='comb')
        wp = mem.write_port()

        m.d.comb += [
            rp.addr.eq(r_ptr - 1),
            self.head.eq(rp.data),
        ]

        with m.If(self.pop.req.valid):
            m.d.sync += r_ptr.eq(r_ptr - 1)

        with m.If(self.push.req.valid):
            m.d.sync += r_ptr.eq(r_ptr + 1)
            m.d.comb += [
                wp.en.eq(self.push.req.valid),
                wp.data.eq(self.push.req.addr),
                wp.addr.eq(r_ptr),
            ]


        #m.d.comb += [
        #    #rp.en.eq(self.req.valid),
        #    rp.addr.eq(self.req.idx),
        #    wp.en.eq(self.write_req.valid),
        #    wp.addr.eq(self.write_req.idx),
        #    wp.data.eq(self.write_req.addr),
        #]

        #bypass_match = (self.write_req.idx == self.req.idx)
        #can_bypass = (self.write_req.valid & bypass_match)
        #result = Mux(can_bypass, self.write_req.addr, rp.data)
        #m.d.sync += [
        #    self.resp.valid.eq(self.req.valid),
        #    self.resp.addr.eq(Mux(self.req.valid, result, 0)),
        #    self.resp.idx.eq(self.req.idx),
        #]
        return m




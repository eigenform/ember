

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from struct import pack, unpack
#from hexdump import hexdump


class FakeRamRequest(Signature):
    def __init__(self):
        super().__init__({
            "valid": Out(1),
            "addr": Out(32),
        })
class FakeRamResponse(Signature):
    def __init__(self, width_words: int):
        super().__init__({
            "valid": Out(1),
            "data": Out(unsigned(32)).array(width_words),
        })

class FakeRamInterface(Signature):
    def __init__(self, width_words: int):
        self.width_words = width_words
        super().__init__({
            "req": Out(FakeRamRequest()),
            "resp": In(FakeRamResponse(width_words)),
        })

class PendingRead(object):
    def __init__(self, addr: int):
        self.addr = addr
        self.valid = False

class FakeRam(object):
    """ An imaginary RAM device for use during simulation. 
    """

    class FakeRamPipe(object):
        def __init__(self):
            self.valid = False
            self.addr  = 0

    def __init__(self, size: int):
        self.width_words = 8
        self.data = bytearray(size)
        self.size = size
        self.cycle = 0

        self.pipes = [ self.FakeRamPipe() for _ in range(2) ]

        self.valid = False
        self.addr = 0

    def run(self, req: FakeRamRequest, resp: FakeRamResponse, pipe=0):
        assert len(resp.data) == self.width_words, "width mismatch?"

        # Sample the request wires
        req_valid = yield req.valid
        req_addr  = yield req.addr
        assert req_addr < self.size, f"FakeRam oob request @ {req_addr:08x}"

        if self.pipes[pipe].valid: 
            data = self.read_words(self.pipes[pipe].addr, self.width_words)
            for idx in range(self.width_words):
                yield resp.data[idx].eq(data[idx])
            yield resp.valid.eq(True)
        else:
            for idx in range(self.width_words):
                yield resp.data[idx].eq(0)
            yield resp.valid.eq(False)

        if req_valid != 0:
            self.pipes[pipe].valid = True
            self.pipes[pipe].addr  = req_addr
        else:
            self.pipes[pipe].valid = False
            self.pipes[pipe].addr  = 0
        return

    def read_word(self, offset: int): 
        value = unpack("<L", self.data[offset:offset+4])[0]
        return value

    def write_word(self, offset: int, value: int):
        data = pack("<L", value)
        self.data[offset:offset+4] = bytearray(data)

    def read_words(self, offset: int, size: int):
        values = unpack(f"<{size}L", self.data[offset:offset+(4*size)])
        return values

    def read_bytes(self, offset: int, size: int):
        data = self.data[offset:offset+size]
        return bytearray(data)

    def write_bytes(self, offset:int, data: bytearray):
        self.data[offset:offset+len(data)] = data




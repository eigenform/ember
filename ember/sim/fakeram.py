

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from struct import pack, unpack
#from hexdump import hexdump

class FakeRamRequest(Signature):
    def __init__(self, width_words: int = 4):
        super().__init__({
            "valid": Out(1),
            "offset": Out(32),
        })
class FakeRamResponse(Signature):
    def __init__(self, width_words: int = 4):
        super().__init__({
            "valid": Out(1),
            "data": Out(ArrayLayout(unsigned(32), width_words)),
        })

class FakeRamInterface(Signature):
    def __init__(self, width_words: int = 4):
        super().__init__({
            "req": Out(FakeRamRequest(width_words)),
            "resp": In(FakeRamResponse(width_words)),
        })




class FakeRam(object):
    """ An imaginary RAM device for use during simulation. 
    """
    def __init__(self, size: int):
        self.data = bytearray(size)
        self.size = size

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




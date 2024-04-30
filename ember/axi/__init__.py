
from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
from amaranth.utils import log2_int, exact_log2

class AXIBurst(Enum):
    FIXED    = 0b00
    INCR     = 0b01
    WRAP     = 0b10
    RESERVED = 0b11

class AXIResp(Enum):
    OKAY   = 0b00
    EXOKAY = 0b01
    SLVERR = 0b10
    DECERR = 0b11

class AXISize(Enum):
    Byte1  = 0b000
    Byte2  = 0b001
    Byte4  = 0b010
    Byte8  = 0b011
    Byte16 = 0b100
    Byte32 = 0b110
    Byte64 = 0b111

class AXIConfig(object):
    def __init__(self, addr_width, data_width, 
                 id_width, lock_width, size_width):
        assert data_width % 8 == 0
        self.addr_width = addr_width
        self.data_width = data_width
        self.id_width = id_width
        self.lock_width = lock_width
        self.size_width = size_width


class AXIAddrChannel(Signature):
    def __init__(self, cfg: AXIConfig):
        self.cfg = cfg
        super().__init__({
            "addr": Out(cfg.addr_width),
            "size": Out(AXISize),
            "len":  Out(8),
            "burst": Out(AXIBurst),
            "id": Out(cfg.id_width),
            "lock": Out(cfg.lock_width),
            "cache": Out(4),
            "prot": Out(3),
            "qos": Out(4),
        })

class AXIWriteDataChannel(Signature):
    def __init__(self, cfg: AXIConfig):
        self.cfg = cfg
        super().__init__({
            "data": Out(cfg.data_width),
            "strb": Out(cfg.data_width // 8),
            "last": Out(1),
        })

class AXIWriteRespChannel(Signature):
    def __init__(self, cfg: AXIConfig):
        self.cfg = cfg
        super().__init__({
            "id": Out(cfg.id_width),
            "resp": Out(AXIResp),
        })

class AXIReadDataChannel(Signature):
    def __init__(self, cfg: AXIConfig):
        self.cfg = cfg
        super().__init__({
            "data": Out(cfg.data_width),
            "id": Out(cfg.id_width),
            "last": Out(1),
            "resp": Out(AXIResp),
        })

class AXISourcePort(Signature):
    def __init__(self, cfg: AXIConfig):
        self.cfg = cfg
        super().__init__({
            "waddr": Out(AXIAddrChannel(cfg)),
            "wdata": Out(AXIWriteDataChannel(cfg)),
            "wresp": In(AXIWriteRespChannel(cfg)),
            "raddr": Out(AXIAddrChannel(cfg)),
            "rdata": In(AXIReadDataChannel(cfg)),
        })

class AXISinkPort(Signature):
    def __init__(self, cfg: AXIConfig):
        self.cfg = cfg
        super().__init__({
            "waddr": In(AXIAddrChannel(cfg)),
            "wdata": In(AXIWriteDataChannel(cfg)),
            "wresp": Out(AXIWriteRespChannel(cfg)),
            "raddr": In(AXIAddrChannel(cfg)),
            "rdata": Out(AXIReadDataChannel(cfg)),
        })



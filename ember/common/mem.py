
from amaranth import *
from amaranth import ShapeCastable
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.enum import *
import amaranth.lib.memory as memory
from amaranth.utils import ceil_log2, exact_log2

class BankedMemoryInterface(Signature):
    class ReadPort(Signature):
        class Request(Signature):
            def __init__(self, depth: int):
                super().__init__({
                    "valid": Out(1),
                    "addr": Out(ceil_log2(depth)),
                })

        class Response(Signature):
            def __init__(self, data_shape: Shape):
                super().__init__({
                    "valid": Out(1),
                    "data": Out(data_shape),
                })

        def __init__(self, depth: int, data_shape: Shape):
            super().__init__({
                "req": Out(self.Request(depth)),
                "resp": In(self.Response(data_shape)),
            })

    class WritePort(Signature):
        class Request(Signature):
            def __init__(self, depth: int, data_shape: Shape):
                super().__init__({
                    "valid": Out(1),
                    "addr": Out(ceil_log2(depth)),
                    "data": Out(data_shape),
                })
        class Response(Signature):
            def __init__(self):
                super().__init__({
                    "valid": Out(1),
                })

        def __init__(self, depth: int, data_shape: Shape):
            super().__init__({
                "req": Out(self.Request(depth, data_shape)),
                "resp": In(self.Response()),
            })

    def __init__(self, depth: int, data_shape: Shape):
        super().__init__({
            "rp": Out(self.ReadPort(depth, data_shape)),
            "wp": Out(self.WritePort(depth, data_shape)),
        })



class BankedMemory(Component):
    """ A set of banked memory elements. 

    Each bank has a single read port and a single write port (with bypassing).
    """
    def __init__(self, num_banks: int, depth: int, data_shape: ShapeCastable):
        self.num_banks = num_banks
        self.depth = depth
        self.data_shape = data_shape
        sig = Signature({
            "bank": In(BankedMemoryInterface(depth, data_shape))
                    .array(num_banks),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        for idx in range(self.num_banks):
            iface = self.bank[idx]
            bank = m.submodules[f"bank{idx}"] = memory.Memory(
                shape=self.data_shape,
                depth=self.depth,
                init=[],
            )
            wp = bank.write_port()
            rp = bank.read_port(transparent_for=[wp])
            m.d.comb += [
                wp.en.eq(iface.wp.req.valid),
                wp.addr.eq(iface.wp.req.addr),
                wp.data.eq(iface.wp.req.data),
                rp.en.eq(iface.rp.req.valid),
                rp.addr.eq(iface.rp.req.addr),
                iface.rp.resp.data.eq(rp.data),
            ]
            m.d.sync += [
                iface.rp.resp.valid.eq(iface.rp.req.valid),
                iface.wp.resp.valid.eq(iface.wp.req.valid),
            ]

        return m




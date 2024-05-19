from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2, exact_log2

class GenericReadPort(Signature):
    class Request(Signature):
        def __init__(self, index_shape: Shape):
            super().__init__({
                "valid": Out(1),
                "addr": Out(index_shape),
            })
    class Response(Signature):
        def __init__(self, data_shape: Shape):
            super().__init__({
                "valid": Out(1),
                "data": Out(data_shape),
            })
    def __init__(self, index_shape: Shape, data_shape: Shape):
        super().__init__({
            "req": Out(self.Request(index_shape)),
            "resp": In(self.Response(data_shape)),
        })


class GenericWritePort(Signature):
    class Request(Signature):
        def __init__(self, index_shape: Shape, data_shape: Shape):
            super().__init__({
                "valid": Out(1),
                "addr": Out(index_shape),
                "data": Out(data_shape),
            })
    class Response(Signature):
        def __init__(self):
            super().__init__({
                "valid": Out(1),
            })
    def __init__(self, index_shape: Shape, data_shape: Shape):
        super().__init__({
            "req": Out(self.Request(index_shape, data_shape)),
            "resp": In(self.Response()),
        })





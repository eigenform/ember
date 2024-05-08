import unittest
import functools
import itertools
import operator

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.hdl._ir import PortDirection
from amaranth.utils import ceil_log2, exact_log2, bits_for
from amaranth.sim import *
from amaranth.back import verilog

from ember.sim.common import *
from ember.common.queue import *
from ember.common import *

class QueueHarness(object):
    def __init__(self, dut: Queue):
        self.dut = dut

    def drive(self, push_data, push_size, pop_size):
        assert len(push_data) <= self.dut.width
        for idx in range(self.dut.width):
            if idx < len(push_data):
                yield self.dut.i_push_data[idx].eq(push_data[idx])
            else:
                yield self.dut.i_push_data[idx].eq(0)
        yield self.dut.i_push_size.eq(push_size)
        yield self.dut.i_pop_size.eq(pop_size)

    def sample(self):
        pop_limit  = yield self.dut.o_pop_limit
        push_limit = yield self.dut.o_push_limit
        of = yield self.dut.o_overflow
        uf = yield self.dut.o_underflow
        data = []
        for idx in range(self.dut.width):
            x = yield self.dut.o_data[idx]
            data.append(x)
        return (data, push_limit, pop_limit, of, uf)

def tb_queue_overflow(dut: Queue):
    q = QueueHarness(dut)
    d = [ i for i in range(1, 33) ]
    data = list(chunks(d, 4))
    for i in range(8):
        yield from q.drive(data[i], 4, 0)
        yield Tick()
    # Try to push more data onto the queue
    out_data, push_limit, pop_limit, of, uf = yield from q.sample()
    assert push_limit == 0
    yield from q.drive(data[0], 4, 0)
    yield Tick()
    # The overflow signal should be asserted
    out_data, push_limit, pop_limit, of, uf = yield from q.sample()
    assert of == 1
    assert pop_limit == 4

def tb_queue_underflow(dut: Queue):
    q = QueueHarness(dut)

    # Try to pop data from an empty queue
    out_data, push_limit, pop_limit, of, uf = yield from q.sample()
    assert pop_limit == 0
    yield from q.drive([0,0,0,0], 0, 4)
    yield Tick()

    # The underflow signal should be asserted
    out_data, push_limit, pop_limit, of, uf = yield from q.sample()
    assert uf == 1
    assert pop_limit == 0
    yield from q.drive([0,0,0,0], 0, 0)
    yield Tick()

    # Push one element onto the queue
    yield from q.drive([1,0,0,0], 1, 0)

    # Try to pop more than one element from the queue
    yield Tick()
    yield from q.drive([1,0,0,0], 0, 4)

    yield Tick()
    # The underflow signal should be asserted
    out_data, push_limit, pop_limit, of, uf = yield from q.sample()
    assert uf == 1
    assert pop_limit == 1


def tb_queue_wrap(dut: Queue):
    q = QueueHarness(dut)
    d = [ i for i in range(1, 256) ]
    data = list(chunks(d, 4))
    yield from q.drive(data[0], 4, 0)
    yield Tick()

    for i in range(1,32):
        out_data, push_limit, pop_limit, of, uf = yield from q.sample()
        yield from q.drive(data[i], 4, 4)
        yield Tick()



class QueueUnitTests(unittest.TestCase):
    def test_queue_elab(self):
        dut = Queue(32, 4, unsigned(32))
        with open("/tmp/QueueTest.v", "w") as f:
            f.write(verilog.convert(dut))

    def test_queue_overflow(self):
        tb = Testbench(
            Queue(32, 4, unsigned(32)),
            tb_queue_overflow,
            "tb_queue_overflow"
        )
        tb.run()

    def test_queue_underflow(self):
        tb = Testbench(
            Queue(32, 4, unsigned(32)),
            tb_queue_underflow,
            "tb_queue_underflow"
        )
        tb.run()

    def test_queue_wrap(self):
        tb = Testbench(
            Queue(32, 4, unsigned(32)),
            tb_queue_wrap,
            "tb_queue_wrap"
        )
        tb.run()





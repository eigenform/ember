import unittest
import functools
import itertools
import operator
import random

from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.hdl._ir import PortDirection
from amaranth.utils import ceil_log2, exact_log2, bits_for
from amaranth.sim import *
from amaranth.back import verilog

from ember.sim.common import *
from ember.common.queue import *
from ember.common.pipeline import *
from ember.common import *

class CreditQueueHarness(Component):
    def __init__(self, width: int, depth: int):
        self.width = width
        self.depth = depth
        self.stage = PipelineStages()
        self.stage.add_stage(1, {
            "size": unsigned(ceil_log2(self.width+1)),
            "value": ArrayLayout(unsigned(32), self.width),
        })
        self.stage.add_stage(2, {
            "size": unsigned(ceil_log2(self.width+1)),
            "value": ArrayLayout(unsigned(32), self.width),
        })
        self.stage.add_stage(3, {
            "size": unsigned(ceil_log2(self.width+1)),
            "value": ArrayLayout(unsigned(32), self.width),
        })

        super().__init__(Signature({
            "up": In(CreditQueueUpstream(self.width, unsigned(32))),
        }))


        return

    def elaborate(self, platform):
        m = Module()
        clk_ctr = Signal(8, init=1)
        m.d.sync += clk_ctr.eq(clk_ctr + 1)

        q = m.submodules.q = CreditQueue(self.depth, self.width, unsigned(32))
        connect(m, flipped(self.up), q.up)
        #m.d.comb += [q.wr_data[idx].eq(self.wr_data[idx]) for idx in range(self.width)]

        #m.d.sync += Print(Format("rd_credit={}", q.down.credit.avail.credit))

        avail_credit = q.down.credit.avail.credit
        with m.If(avail_credit > 0):
            m.d.comb += q.down.credit.req.credit.eq(avail_credit)
            m.d.comb += q.down.credit.req.valid.eq(1)
            #for idx in range(self.width):
            #    with m.If(idx < avail_credit):
            #        m.d.sync += Print(Format("{:08x}", q.down.data[idx]))
        with m.Else():
            m.d.comb += q.down.credit.req.credit.eq(0)
            m.d.comb += q.down.credit.req.valid.eq(0)

        return m

#def tb_credit_queue(dut: CreditQueue):
#    print()
#    rd_credits = yield dut.rd_credit.avail.credit
#    wr_credits = yield dut.wr_credit.avail.credit

def tb_credit_pipe(dut: CreditQueueHarness):
    #print()
    cycles = 1

    while True: 
        wr_credits = yield dut.up.credit.avail.credit
        #print(f"wr_credits={wr_credits}")
        if wr_credits == 0: 
            break
        if wr_credits == 1: 
            x = 1
        else: 
            x = random.randrange(0, wr_credits+1)
        #print(f"writing {x} entries")
        yield dut.up.credit.req.credit.eq(x)
        yield dut.up.credit.req.valid.eq(1)
        for idx in range(4):
            if idx < x:
                yield dut.up.data[idx].eq(cycles << 16 | idx)
            else:
                yield dut.up.data[idx].eq(0)
        yield Tick()
        if cycles > 32: break
        cycles += 1

    wr_credits = yield dut.up.credit.avail.credit
    #print(f"wr_credits={wr_credits}")








class CreditQueueUnitTests(unittest.TestCase):
    #def test_credit_queue(self):
    #    tb = Testbench(
    #        CreditQueue(32, 4, unsigned(32)),
    #        tb_credit_queue,
    #        "tb_credit_queue"
    #    )
    #    tb.run()

    def test_credit_pipe(self):
        tb = Testbench(
            CreditQueueHarness(4, 32),
            tb_credit_pipe,
            "tb_credit_pipe"
        )
        tb.run()










import inspect
import logging
from amaranth import *
from amaranth.sim import *
from amaranth.back import verilog, rtlil

#class Harness(object):
#    """ Container for wrapping the device-under-test during simulation.
#    The user is expected to inherit this class and implement methods for
#    driving/sampling different signals during simulation. 
#    """
#    def __init__(self, dut: Elaboratable):
#        self.dut = dut

class TestbenchComb(object):
    def __init__(self, dut: Elaboratable, proc, vcd_name=""):
        self.vcd_name = vcd_name
        self.dut = dut
        self.sim = Simulator(self.dut)
        self.sim.add_process(self.process)
        assert inspect.isgeneratorfunction(proc)
        self.proc = proc
        self.cycle = 0

    def step(self):
        if self.cycle == 0:
            yield Tick()
        else:
            yield Tick()
            yield Tick()
        self.cycle += 1

    def process(self):
        yield from self.proc(self.dut)

    def run(self):
        if self.vcd_name != "":
            path = f"/tmp/{self.vcd_name}.vcd"
            with open(path, "w") as f:
                with self.sim.write_vcd(vcd_file=f):
                    self.sim.run()
        else:
            self.sim.run()




class Testbench(object):
    """ Boilerplate simple testbench """
    def __init__(self, dut: Elaboratable, proc, vcd_name=""):
        self.vcd_name = vcd_name
        self.dut = dut
        self.sim = Simulator(self.dut)
        self.sim.add_clock(1e-6)
        self.sim.add_testbench(self.process)
        assert inspect.isgeneratorfunction(proc)
        self.proc = proc
        self.cycle = 0

    def step(self):
        if self.cycle == 0:
            yield Tick()
        else:
            yield Tick()
            yield Tick()
        self.cycle += 1

    def process(self):
        yield from self.proc(self.dut)

    def run(self):
        if self.vcd_name != "":
            path = f"/tmp/{self.vcd_name}.vcd"
            with open(path, "w") as f:
                with self.sim.write_vcd(vcd_file=f):
                    self.sim.run()
        else:
            self.sim.run()


class ClkTimer(object):
    def __init__(self, name: str, start=None, limit=None):
        self.name = name
        self.start = start
        self.limit = limit
        self.end   = None
    def is_done(self):
        return (self.start != None) and (self.end != None)
    def clear(self): 
        self.start = None
        self.end   = None
    def elapsed(self): 
        if not self.is_done():
            return -1
        else: 
            return self.end - self.start

class ClkMgr(object):
    """ Simple book-keeping for timers during simulation. 
    """
    def __init__(self):
        self.cycle = 0
        self.events = {}

    def start(self, name: str, limit=None): 
        if name in self.events:
            self.events[name].start = self.cycle
        else: 
            self.events[name] = ClkTimer(name, start=self.cycle, limit=limit)

    def stop(self, name: str):
        assert name in self.events
        if self.events[name].end == None:
            self.events[name].end = self.cycle

    def elapsed(self, name: str):
        return self.events[name].elapsed()

    def step(self):
        yield Tick()
        self.cycle += 1
        for name, event in self.events.items(): 
            if (event.limit == None) or event.is_done(): 
                continue
            if (self.cycle - event.start) >= event.limit: 
                raise ValueError("[ClkMgr] {:36} reached {}-cycle limit".format(
                    name, event.limit
                ))

    def print_events(self):
        for name, event in self.events.items():
            if event.end == None:
                print("[ClkMgr] {:36}: not completed".format(name))
                continue

            if event.limit == None:
                print("[ClkMgr] {:36}: {} cycles elapsed".format(
                    name, event.elapsed()
                ))
            else:
                print("[ClkMgr] {:36}: {} cycles elapsed (limit={})".format(
                    name, event.elapsed(), event.limit
                ))



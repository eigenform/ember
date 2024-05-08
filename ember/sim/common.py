
import inspect
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




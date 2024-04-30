
from amaranth import *
from amaranth.hdl.ast import ShapeCastable
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *

class PipelineStages(object):
    def __init__(self):
        self.stages = {}
    def __getitem__(self, key: int):
        if key not in self.stages:
            raise ValueError(f"Undefined pipeline stage {key}")
        return self.stages[key]

    def add_stage(self, idx: int, signals: dict[str,ShapeCastable]):
        self.stages[idx] = PipelineStage(idx, signals)

class PipelineStage(object):
    """ Simple container for signals in a pipeline """
    _reserved_names = [ "ready", "valid" ]
    def __init__(self, idx: int, signals: dict[str,ShapeCastable]):
        self._stage_idx = idx
        self.ready = Signal(unsigned(1), name=f"stage{idx}_ready")
        self.valid = Signal(unsigned(1), name=f"stage{idx}_valid")
        self.busy = Signal(unsigned(1), name=f"stage{idx}_busy")
        for name, shape in signals.items():
            if name in self._reserved_names: 
                raise ValueError(
                    f"'{name}' is automatically defined for PipelineStage"
                )
            self.__setattr__(
                name, 
                Signal(shape, name=f"stage{idx}_{name}")
            )

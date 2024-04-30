from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2, exact_log2

def gen_tree_indexes(num_entries):
    num_entries_log2 = exact_log2(num_entries)
    res = {}
    for entry_idx in range(num_entries):
        res[entry_idx] = []
        for bit_idx in range(num_entries_log2):
            base = (1 << bit_idx) - 1
            off  = num_entries_log2 - bit_idx
            res[entry_idx].append(base + (entry_idx >> off))
    return res

#class ReplacementPolicyInterface(Signature):
#    def __init__(self, num_entries):
#        super().__init__({
#        })

class TreePLRU(Component):
    """ The binary tree version of a "Pseudo Least-Recently Used" policy. 
    NOTE: The number of entries must be a power of two. 
    """
    def __init__(self, num_entries: int):
        assert num_entries.bit_count() == 1
        self.num_entries = num_entries
        self.idx_width   = exact_log2(num_entries)
        self.possible_indexes = [ i for i in range(self.num_entries) ]

        signature = Signature({
            "access": In(self.idx_width),
            "lru": Out(self.idx_width),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        tree_state = Array(Signal() for _ in range(self.num_entries-1))

        index_map = gen_tree_indexes(self.num_entries)
        print(index_map)

        m.d.sync += [ ]
        return m 






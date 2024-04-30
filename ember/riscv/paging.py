
from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.utils import log2_int

class VirtualPageNumberSv32(StructLayout):
    """ An Sv32 virtual page number """
    def __init__(self):
        super().__init__({
            'vpn0': unsigned(10),
            'vpn1': unsigned(10),
        })

class PhysicalPageNumberSv32(StructLayout):
    """ An Sv32 physical page number """
    def __init__(self):
        super().__init__({
            'ppn0': unsigned(10),
            'ppn1': unsigned(12),
        })



class SatpSv32(StructLayout):
    """ Layout of the Sv32 SATP CSR """
    def __init__(self):
        super().__init__({
            'ppn': PhysicalPageNumberSv32(),
            'asid': unsigned(9),
            'mode': unsigned(1),
        })


class VirtualAddressSv32(StructLayout):
    """ An Sv32 virtual address """
    def __init__(self):
        super().__init__({
            'offset': unsigned(12),
            'vpn': VirtualPageNumberSv32(),
        })

class PhysicalAddressSv32(StructLayout):
    """ An Sv32 physical address """
    def __init__(self):
        super().__init__({
            'offset': unsigned(12),
            'ppn': PhysicalPageNumberSv32(),
        })

class PageTableEntrySv32(StructLayout):
    """ An Sv32 page table entry"""
    def __init__(self):
        super().__init__({
            'v': unsigned(1),
            'r': unsigned(1),
            'w': unsigned(1),
            'x': unsigned(1),
            'u': unsigned(1),
            'g': unsigned(1),
            'a': unsigned(1),
            'd': unsigned(1),
            'rsw': unsigned(2),
            'ppn': PhysicalPageNumberSv32(),
        })



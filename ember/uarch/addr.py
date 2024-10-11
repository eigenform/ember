from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.lib.coding import *
from amaranth.lib.enum import *
from amaranth.utils import ceil_log2, exact_log2

from ember.riscv.paging import *

class CacheLine(ArrayLayout):
    def __init__(self, word_bits, num_words):
        super().__init__(word_bits, num_words)

#self.vaddr_layout = StructLayout({
#    'wrd': unsigned(2),
#    'off': unsigned(self.num_off_bits),
#    'idx': unsigned(self.num_idx_bits),
#    'tag': unsigned(self.num_tag_bits),
#})

# Sv32 virtual addresses are organized like this:
# 
#   31                  15                0
#   v                   v                 v
#   .... .... .... .... .... xxxx xxxx xxxx - Sv32 virtual page offset
#   .... .... ..xx xxxx xxxx .... .... .... - Sv32 virtual page number 0
#   xxxx xxxx xx.. .... .... .... .... .... - Sv32 virtual page number 1
#   ------------------------------------------------------------------
#
# Assuming 32-byte cachelines, a virtual address would be decomposed into:
#
#   31                  15                0
#   v                   v                 v
#   .... .... .... .... .... .... .... ..xx - Byte index within a word
#   .... .... .... .... .... .... ...x xx.. - Word index
#   .... .... .... .... .... .... ...x xxxx - Byte index within a cacheline
#   .... .... .... .... .... xxxx xxx. .... - Line index within a virtual page
#   xxxx xxxx xxxx xxxx xxxx .... .... .... - Tag bits
#   ------------------------------------------------------------------

class L1IAddressLayout(FlexibleLayout):
    """ Address bits used for interacting with the L1I cache. 

    Fields
    ======
    off:
        Offset of a byte within a cacheline
    set:
        The L1I cache set index for a cacheline
    line:
        The index of a cacheline within a physical page

    """
    def __init__(self, cache_line_sz: int, cache_sets: int):
        self.num_offset_bits = exact_log2(cache_line_sz)
        self.num_set_bits    = exact_log2(cache_sets)
        self.num_line_bits   = 12 - self.num_offset_bits

        self.offset_bits_idx = 0
        self.set_bits_idx    = self.offset_bits_idx + self.num_offset_bits
        self.line_bits_idx   = self.offset_bits_idx + self.num_offset_bits

        assert (self.num_offset_bits + self.num_set_bits) <= 12
        assert (self.set_bits_idx <= 12)

        super().__init__(12, {
            # Offset of a byte within a cacheline
            "off":  Field(self.num_offset_bits, self.offset_bits_idx),
            # The L1I set index
            "set": Field(self.num_set_bits, self.set_bits_idx),
            # Index of a line within the page
            "line": Field(self.num_line_bits, self.line_bits_idx),
        })


class VirtualAddress(FlexibleLayout):
    """ Layout of a 32-bit virtual address. 

    Fields
    ======
    bits:
        Flat unsigned integer layout.
    sv32:
        Layout associated with the Sv32 virtual memory scheme.
    l1i:
        Layout used to access the L1I cache
    """
    def __init__(self, l1i_line_bytes: int, l1i_num_sets: int):
        self.num_line_bytes = l1i_line_bytes
        self.num_off_bits = exact_log2(l1i_line_bytes)
        self.num_blk_bits = 32 - self.num_off_bits
        super().__init__(32, {
            "bits":    Field(unsigned(32), 0),
            "sv32":    Field(VirtualAddressSv32(), 0),
            "l1i":     Field(L1IAddressLayout(l1i_line_bytes, l1i_num_sets), 0),

            "fetch_off": Field(unsigned(self.num_off_bits), 0),
            "fetch_blk": Field(unsigned(self.num_blk_bits), self.num_off_bits),
        })

    def __call__(self, value):
        return VirtualAddressView(self, value)

class VirtualAddressView(View):
    """ View associated with a virtual address. """
    def __init__(self, layout: VirtualAddress, target):
        assert isinstance(layout, VirtualAddress)
        self.num_line_bytes = layout.num_line_bytes
        self.num_off_bits = layout.num_off_bits
        self.num_blk_bits = layout.num_blk_bits
        super().__init__(layout, target)

    def get_fetch_off(self):
        return self.fetch_off

    def get_fetch_addr(self):
        """ Return a full 32-bit address with the offset bits set to zero """
        res = Cat(C(0, self.num_off_bits), self.fetch_blk)
        assert len(res) == 32
        return res

class PhysicalAddress(FlexibleLayout):
    """ Layout of a 34-bit physical address. """
    def __init__(self, l1i_line_bytes: int, l1i_num_sets: int):
        super().__init__(34, {
            "bits": Field(unsigned(34), 0),
            "sv32": Field(PhysicalAddressSv32(), 0),
            "l1i":  Field(L1IAddressLayout(l1i_line_bytes, l1i_num_sets), 0),
        })



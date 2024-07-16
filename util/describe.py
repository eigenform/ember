
""" describe.py

Print a summary of the design parameters to stdout. 
"""

#from ember.param import *
#from ember.uarch.fetch import *
#from ember.front.predecode import PredecodeInfo

#from amaranth import *
#from amaranth.sim import *
#from amaranth.lib.enum import *
#from amaranth.back import verilog, rtlil


#def info(desc: str, info: str): 
#    print("  {:<30}: {}".format(desc, info))
#
#p = EmberParams()
#
#print("[*] EmberParams summary:")
#
#info("Superscalar width", "{}-wide".format(
#    p.superscalar_width
#))
#info("Fetch width", "{} instructions".format(
#    p.fetch.width
#))
#info("Decode width", "{} instructions".format(
#    p.decode.width
#))
#
#
#print()
#
#info("L1I associativity", "{} sets, {} ways".format(
#    p.l1i.num_sets, p.l1i.num_ways
#))
#info("L1I line size", "{} (0x{:02x}) bytes".format(
#    p.l1i.line_bytes, p.l1i.line_bytes
#))
#info("L1I footprint (data)", "{} bits ({}B)".format(
#    p.l1i.data_footprint_bits, 
#    p.l1i.data_footprint_bits // 8
#))
#info("L1I footprint (tag)", "{} bits ({}B)".format(
#    p.l1i.tag_footprint_bits, 
#    p.l1i.tag_footprint_bits // 8
#))
#print()
#
#info("L1I TLB capacity", "{} entries".format(
#    p.l1i.tlb.num_entries()
#))
##info("L1I TLB footprint (data)", "{} bits ({}B)".format(
##    p.l1i.tlb.data_footprint_bits(),
##    p.l1i.tlb.data_footprint_bits() // 8,
##))
##info("L1I TLB footprint (tag)", "{} bits ({}B)".format(
##    p.l1i.tlb.tag_footprint_bits(),
##    p.l1i.tlb.tag_footprint_bits() // 8,
##))
#print()
#
#info("PredecodeInfo footprint", "{} bits".format(
#    PredecodeInfo(p.vaddr).size
#))
#
#info("L0 BTB capacity", "{} entries".format(
#    p.bp.l0_btb_depth
#))
##info("L0 BTB footprint (data)", "{} bits ({}B)".format(
##    p.bp.l0_btb_data_shape.size * p.bp.l0_btb_depth,
##    (p.bp.l0_btb_data_shape.size * p.bp.l0_btb_depth) // 8
##))
##info("L0 BTB footprint (tag)", "{} bits ({}B)".format(
##    p.bp.l0_btb_tag_shape.width * p.bp.l0_btb_depth,
##    (p.bp.l0_btb_tag_shape.width * p.bp.l0_btb_depth) // 8
##))
#print()
#
#
#info("FTQ capacity", "{} entries".format(
#    p.fetch.ftq_depth
#))
#info("FTQ footprint", "{} bits ({}B)".format(
#    FTQEntry(p).size * p.fetch.ftq_depth,
#    (FTQEntry(p).size * p.fetch.ftq_depth) // 8,
#))
#info("FTQEntry footprint", "{} bits".format(
#    FTQEntry(p).size
#))
#print()
#
#info("Virtual address (block bits)", "{} bits".format(
#    p.vaddr.num_blk_bits
#))
#info("Virtual address (offset bits)", "{} bits".format(
#    p.vaddr.num_off_bits
#))
#
#
#
#info("EmberMop footprint", "{} bits".format(
#    EmberMop.layout.size
#))


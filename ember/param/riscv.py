

class RiscvParams(object):
    """ RISC-V ISA parameters. 

    Attributes
    ==========
    reset_vector:
        The program counter value on reset

    """
    xlen         = 32
    xlen_bits    = xlen
    xlen_bytes   = (xlen_bits // 8)

    # NOTE: The reset vector is implementation-defined.
    reset_vector = 0x0000_0000

    # Sv32 only uses 4KiB pages (???)
    page_size_bytes = 0x0000_1000




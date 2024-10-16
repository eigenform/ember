
from amaranth import *
from amaranth.utils import ceil_log2, exact_log2
from amaranth.lib.wiring import *
from amaranth.lib.data import *

from ember.param import EmberParams
from ember.param.front import *
from ember.uarch.addr import *
from ember.uarch.mop import *

class ResteerRequest(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "op": Out(ControlFlowOp),
            "src_pc": Out(p.vaddr),
            "tgt_pc": Out(p.vaddr),
            "parent_ftq_idx": Out(p.ftq.index_shape),
            "parent_line": Out(p.fblk_size_shape),
            "parent_idx": Out(p.l1i.word_idx_shape)
        })



class ControlFlowRequest(Signature):
    """ A request to continue the instruction stream at some location.

    Members
    =======
    valid:
        This request is valid
    pc:
        The program counter indicating the next valid instruction 
    blocks:
        The number of sequential cachelines in this request

    parent_ftq_idx:
        The index of the FTQ entry that generated this request. 
    parent_line:
        Cacheline index in the parent fetch block which caused this request.
    parent_idx:
        Word index into the parent cacheline which caused this request. 

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "pc": Out(p.vaddr),
            "op": Out(ControlFlowOp),
            "blocks": Out(p.fblk_size_shape),
            "parent_ftq_idx": Out(p.ftq.index_shape),
            "parent_line": Out(p.fblk_size_shape),
            "parent_idx": Out(p.l1i.word_idx_shape)
        })


class L1ICacheline(ArrayLayout):
    def __init__(self, p: EmberParams):
        super().__init__(unsigned(p.l1i.word_width), p.l1i.line_depth)

class L1ITag(StructLayout):
    def __init__(self):
        super().__init__({
            "valid": unsigned(1),
            "ppn": PhysicalPageNumberSv32(),
        })



#class FTQIndex(Shape):
#    """ An index into the FTQ. """
#    def __init__(self, ftq_depth: int):
#        super().__init__(width=exact_log2(ftq_depth))

class FTQEntryState(Enum, shape=4):
    """ State of an FTQ entry.

    Values
    ======
    NONE:
        FTQ entry is empty
    PENDING:
        Request is eligible for service by the IFU
    PROBE:
        Request stalled for prefetch probe
    FETCH:
        Request stalled for demand fetch
    FILL:
        Request stalled for L1I miss
    XLAT:
        Request stalled for TLB miss
    """
    NONE     = 0
    PROBE    = 1
    FETCH    = 2
    FILL     = 3
    XLAT     = 4

class FTQEntry(StructLayout):
    """ Layout of an entry in the Fetch Target Queue. 

    Members
    =======
    vaddr:
        Program counter value associated with this entry
    state:
        State associated with this entry
    valid:
        Indicates when an entry is valid
    blocks:
        Number of sequential cachelines in this fetch block
    prefetched:
        Indicates when an entry has been prefetched into the L1I cache
    complete:
        Indicates when an entry has been fetched from the L1I cache
    passthru:
        Indicates when the program counter value is a physical address
    id: 
        Identifier for this entry

    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "vaddr": param.vaddr,
            "state": FTQEntryState,
            "blocks": param.fblk_size_shape,
            "valid": unsigned(1),
            "prefetched": unsigned(1),
            "complete": unsigned(1),
            "predicted": unsigned(1),
            "passthru": unsigned(1),
            "id": param.ftq.index_shape,
        })



class DecodeQueueEntry(StructLayout):
    """ Layout of an entry in the decode queue. 

    Members
    =======
    data:
        L1I cacheline data
    ftq_idx:
        FTQ index associated with this entry
    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "data": L1ICacheline(p),
            "ftq_idx": p.ftq.index_shape,
        })

class DemandResponseStatus(Enum, shape=2):
    NONE = 0
    OK = 1
    CANCEL = 2
    RESTEER = 3

class FetchResponseStatus(Enum, shape=2):
    """ Status of a fetch request that has passed through the IFU. 

    Values
    ======
    NONE:
    L1_HIT:
        Request hit in the L1 instruction cache
    L1_MISS:
        Request missed in the L1 instruction cache
    TLB_MISS:
        Request missed in the L1I TLB

    """
    NONE     = 0
    L1_HIT   = 1
    L1_MISS  = 2
    TLB_MISS = 3

class FetchRequest(Signature):
    """ A request to fetch a cache line at some virtual address. 

    Members
    =======
    vaddr:
        Virtual address of the requested cacheline
    passthru: 
        Bypass virtual-to-physical translation

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready": In(1),
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "passthru": Out(1),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class FetchResponse(Signature):
    """ Response to a fetch request.

    Members
    =======
    valid: 
        This response is valid
    vaddr:
        Virtual address associated with this response
    sts: :class:`FetchResponseStatus`
        Status associated with this response
    data:
        Response data (an L1I cache line)
    ftq_idx:
        FTQ index responsible for the associated request

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(FetchResponseStatus),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class FetchData(Signature):
    """ Response data associated with a demand fetch request. 

    Members
    =======
    valid:
        This data is valid
    vaddr:
        Program counter value used to fetch this data
    ftq_idx:
        Index of the associated FTQ entry
    data:
        L1I cacheline data

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "ftq_idx": Out(p.ftq.index_shape),
            "data": Out(L1ICacheline(p)),
            "mask": Out(p.l1i.line_depth),
        })


class PrefetchResponseStatus(Enum, shape=2):
    """ Status for a prefetch request. 

    Values
    ======
    NONE:
    L1_HIT:
        Request hit in the L1 instruction cache
    L1_MISS:
        Request missed in the L1 instruction cache
    TLB_MISS:
        Request missed in the L1I TLB
    """
    NONE     = 0
    L1_HIT   = 1
    L1_MISS  = 2
    TLB_MISS = 3

class PrefetchPipelineStatus(Signature):
    def __init__(self):
        super().__init__({
            "ready": Out(1),
        })

class PrefetchRequest(Signature):
    """ A request to prefetch a cacheline into the L1I cache. 

    Members
    =======
    valid:
        This request is valid
    passthru:
        Treat this virtual address as a physical address.
    ftq_idx:
        The FTQ index responsible for this request.
    vaddr:
        The virtual address of the requested cacheline. 

    """
    def __init__(self, param: EmberParams):
        super().__init__({
            "valid": Out(1),
            "passthru": Out(1),
            "ftq_idx": Out(param.ftq.index_shape),
            "vaddr": Out(param.vaddr),
            "blocks": Out(param.fblk_size_shape),
        })

class PrefetchResponse(Signature):
    """ Response to a prefetch request.

    Members
    =======
    valid: 
        This response is valid
    vaddr:
        Virtual address associated with this response
    sts: :class:`PrefetchResponseStatus`
        Status associated with this response
    ftq_idx:
        FTQ index responsible for the associated request

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "vaddr": Out(p.vaddr),
            "sts": Out(FetchResponseStatus),
            "stall": Out(1),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class PredecodeInfo(StructLayout):
    """ A predecoded RISC-V instruction. 

    Fields
    ======
    ill:
        The encoding for this instruction is invalid/illegal.
    cf_op: :class:`ControlFlowOp`
        Control flow operation associated with this instruction.
    rd: 
        Architectural destination register RD
    rs1: 
        Architectural source register RS1
    imm:
        Extracted immediate value
    tgt:
        Computed target address
    tgt_valid:
        The target address is valid. 


    """
    def __init__(self, vaddr: VirtualAddress):
        self.__vaddr = vaddr
        super().__init__({
            "ill": unsigned(1),
            "is_cf": unsigned(1),
            "cf_op": ControlFlowOp,
            "rd": unsigned(5),
            "rs1": unsigned(5),
            "imm": RvImmData(),
            "tgt": vaddr,
            "tgt_valid": unsigned(1),
        })
    def __call__(self, value):
        return PredecodeInfoView(self.__vaddr, value)


class PredecodeInfoView(View):
    def __init__(self, vaddr: VirtualAddress, target):
        super().__init__(PredecodeInfo(vaddr), target)
    
    def is_direct(self):
        return (
            (self.cf_op == ControlFlowOp.CALL_DIR) |
            (self.cf_op == ControlFlowOp.JUMP_DIR) |
            (self.cf_op == ControlFlowOp.BRANCH)
        )

    def is_indirect(self):
        return (
            (self.cf_op == ControlFlowOp.CALL_IND) |
            (self.cf_op == ControlFlowOp.JUMP_IND) |
            (self.cf_op == ControlFlowOp.RET)
        )

    def resteerable(self):
        return (
            (self.cf_op == ControlFlowOp.CALL_DIR) |
            (self.cf_op == ControlFlowOp.JUMP_DIR) |
            (self.cf_op == ControlFlowOp.RET)
        )



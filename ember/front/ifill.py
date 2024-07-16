from amaranth import *
from amaranth.lib.enum import *
from amaranth.lib.data import *
from amaranth.lib.wiring import *
import amaranth.lib.memory as memory
from amaranth.utils import exact_log2, ceil_log2

from amaranth_soc.wishbone import Interface as WishboneInterface
from amaranth_soc.wishbone import Signature as WishboneSignature

from ember.common import *
from ember.common.coding import EmberPriorityEncoder, ChainedPriorityEncoder
from ember.riscv.paging import *
from ember.param import *
from ember.front.l1i import L1ICacheWritePort
from ember.uarch.front import *
from ember.sim.fakeram import *

class L1IFillRequest(Signature):
    """ L1 instruction cache fill request.

    Ports
    =====
    valid: 
        This request is valid
    addr: 
        Physical address for this request
    way: 
        Target way in the L1I cache

    """
    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "addr": Out(p.paddr),
            "way": Out(ceil_log2(p.l1i.num_ways)),
            "ftq_idx": Out(p.ftq.index_shape),
        })

class L1IFillResponse(Signature):
    """ L1I instruction cache fill response. 

    Members
    =======
    valid:
        This response is valid
    ftq_idx:
        Index of the FTQ entry that generated the request
    """

    def __init__(self, p: EmberParams):
        super().__init__({
            "valid": Out(1),
            "ftq_idx": Out(p.ftq.index_shape),
        })



class L1IFillStatus(Signature):
    def __init__(self, p: EmberParams):
        super().__init__({
            "ready":  Out(1),
        })

class L1IMshrState(Enum, shape=2):
    """ The state associated with an MSHR. 

    Values
    ======
    NONE:
        No request is being serviced.
    ACCESS:
        The request is being serviced by a remote memory device.
    WRITEBACK:
        The request data is available and being written back to the L1I
    COMPLETE:
        The request has been completed and is waiting to be released. 
    """
    NONE      = 0
    ACCESS    = 1
    WRITEBACK = 2
    COMPLETE  = 3 


class L1IMissStatusHoldingRegister(Component):
    """ L1I cache "miss-status holding register" (MSHR)

    The L1I fill unit includes MSHRs that are used to track fill requests 
    generated by both demand fetch and prefetch requests that have missed in 
    the L1I cache. An MSHR holds the request while data is being received 
    from memory and written back to the L1I cache data/tag arrays. 

    An MSHR moves through the following sequence of states:

    - ``L1IMshrState.NONE``: Ready to accept a request
    - ``L1IMshrState.ACCESS``: Request is registered and being sent to memory
    - ``L1IMshrState.WRITEBACK``: Response from memory is registered and being
      sent to the IFU and L1I cache write port
    - ``L1IMshrState.COMPLETE``: L1I cache write port response is acknowledged
      and the state of this MSHR is reset

    Upon completion, the L1I fill unit signals the FTQ indicating that the 
    FTQ entry which generated the fill request is eligible to be replayed.

    Ports
    =====
    ready: 
        High when this MSHR is ready to accept a request
    complete:
        High when this MSHR can be reset
    req: 
        Incoming fill request to this MSHR
    l1i_wp: 
        L1I cache write port interface
    fakeram: 
        Memory interface

    """
    def __init__(self, param: EmberParams):
        self.p = param
        signature = Signature({
            "ready": Out(1),
            "complete": In(1),
            "req": In(L1IFillRequest(param)),
            "resp": Out(L1IFillResponse(param)),
            "l1i_wp": Out(L1ICacheWritePort(param)),
            "fakeram": Out(FakeRamInterface(param.l1i.line_depth)),
        })
        super().__init__(signature)
        return

    def elaborate(self, platform):
        m = Module()

        state   = Signal(L1IMshrState, init=L1IMshrState.NONE)
        addr    = Signal(self.p.paddr)
        way     = Signal(ceil_log2(self.p.l1i.num_ways))
        ftq_idx = Signal(self.p.ftq.index_shape)
        data    = Signal(L1ICacheline(self.p))
        r_ready   = Signal(init=1)

        m.d.comb += self.ready.eq(r_ready)

        with m.Switch(state):

            # Idle state.
            # When we get a request, setup to start access on the next cycle.
            with m.Case(L1IMshrState.NONE):
                with m.If(self.req.valid):
                    m.d.sync += state.eq(L1IMshrState.ACCESS)
                    m.d.sync += r_ready.eq(0)
                    m.d.sync += addr.eq(self.req.addr)
                    m.d.sync += way.eq(self.req.way)
                    m.d.sync += ftq_idx.eq(self.req.ftq_idx)

            # Interact with a memory device until we have a response.
            # When we get a response [after *at least* one cycle], setup for 
            # L1I writeback on the next cycle.
            with m.Case(L1IMshrState.ACCESS):
                m.d.comb += [
                    self.fakeram.req.addr.eq(addr),
                    self.fakeram.req.valid.eq(1),
                ]
                with m.If(self.fakeram.resp.valid):
                    m.d.sync += state.eq(L1IMshrState.WRITEBACK)
                    m.d.sync += data.eq(Cat(*self.fakeram.resp.data))

            # Write the reponse data back to the L1I cache.
            # When we get a response [after *at least* one cycle], setup for
            # sending a fill response
            with m.Case(L1IMshrState.WRITEBACK):
                m.d.comb += [
                    self.l1i_wp.req.valid.eq(1),
                    self.l1i_wp.req.set.eq(addr.l1i.set),
                    self.l1i_wp.req.way.eq(way),
                    self.l1i_wp.req.line_data.eq(data),
                    self.l1i_wp.req.tag_data.ppn.eq(addr.sv32.ppn),
                    self.l1i_wp.req.tag_data.valid.eq(1),
                ]
                with m.If(self.l1i_wp.resp.valid):
                    m.d.sync += state.eq(L1IMshrState.COMPLETE)
                    m.d.sync += self.resp.valid.eq(1)
                    m.d.sync += self.resp.ftq_idx.eq(ftq_idx)

            # Send a fill response until we receive the complete signal.
            # When we get the complete signal, reset to the idle state. 
            with m.Case(L1IMshrState.COMPLETE):
                with m.If(self.complete):
                    m.d.sync += state.eq(L1IMshrState.NONE)
                    m.d.sync += r_ready.eq(1)
                    m.d.sync += addr.eq(0)
                    m.d.sync += way.eq(0)
                    m.d.sync += ftq_idx.eq(0)
                    m.d.sync += self.resp.valid.eq(0)
                    m.d.sync += self.resp.ftq_idx.eq(0)

        return m

class L1IMshrArbiter(Component):
    """ Arbiter for controlling a set of MSHRs. 

    Parameters
    ==========
    num_mshr: int
        The number of MSHRs
    width: int
        The number of fill requests/responses 

    Ports
    =====
    ready:
        High when at least one MSHR is available to service a request.

    ifill_req: L1IFillRequest
        Fill requests to-be-forwarded to available MSHRs.
    ifill_resp: L1IFillResponse
        Fill responses from an MSHR which has completed

    mshr_ready:
        Array of ready signals for each MSHR
    mshr_complete:
        Array of complete signals for each MSHR
    mshr_req: 
        Fill request wires for each MSHR
    mshr_resp:
        Fill response wires for each MSHR

    """
    def __init__(self, param: EmberParams, num_mshr: int, width: int):
        self.p = param
        self.num_mshr = num_mshr
        self.width = width
        sig = Signature({
            "ready": Out(1),
            "ifill_req": In(L1IFillRequest(param)).array(2),
            "ifill_resp": Out(L1IFillResponse(param)).array(2),

            "mshr_ready": In(1).array(num_mshr),
            "mshr_complete": Out(1).array(num_mshr),
            "mshr_req": Out(L1IFillRequest(param)).array(num_mshr),
            "mshr_resp": In(L1IFillResponse(param)).array(num_mshr),
        })
        super().__init__(sig)

    def elaborate(self, platform):
        m = Module()

        # Outgoing requests to MSHRs
        req_arr = Array(
            L1IFillRequest(self.p).create() for _ in range(self.num_mshr)
        )
        # Incoming responses from MSHRs
        resp_arr = Array(
            L1IFillResponse(self.p).flip().create() for _ in range(self.num_mshr)
        )
        # Incoming 'ready' signals from MSHRs
        ready_arr = Array(Signal() for _ in range(self.num_mshr))
        # Incoming 'complete' signals from MSHRs
        complete_arr = Array(Signal() for _ in range(self.num_mshr))

        # Connect ports to intermediate wires
        for idx in range(self.num_mshr):
            connect(m, req_arr[idx], flipped(self.mshr_req[idx]))
            connect(m, flipped(self.mshr_resp[idx]), resp_arr[idx])
            m.d.comb += [
                self.mshr_complete[idx].eq(complete_arr[idx]),
                ready_arr[idx].eq(self.mshr_ready[idx]),
            ]

        # The arbiter is "ready" when at least one MSHR is ready
        m.d.comb += self.ready.eq(Cat(*ready_arr).any())



        # Select up to two free MSHRs
        ready_enc = m.submodules.ready_encoder = \
                ChainedPriorityEncoder(self.num_mshr, depth=2)
        m.d.comb += ready_enc.i.eq(Cat(*ready_arr))
        num_ready = popcount(Cat(*ready_enc.valid))
        num_req   = popcount(Cat([self.ifill_req[ridx].valid for ridx in range(2)]))

        # Select completed MSHRs
        complete_enc = m.submodules.complete_encoder = \
                ChainedPriorityEncoder(self.num_mshr, depth=2)

        valids = [ resp_arr[idx].valid for idx in range(self.num_mshr) ]
        m.d.comb += complete_enc.i.eq(Cat(*valids))
        num_complete = popcount(Cat(*complete_enc.valid))
        #num_resp   = popcount(Cat([self.resp[ridx].valid for ridx in range(2)]))

        #for i in range(2):
        #    m.d.comb += [
        #        Print(Format("IFILL complete slot {}: idx={},valid={}",
        #            idx, complete_enc.o[idx],complete_enc.valid[idx]
        #        ))
        #    ]

        # Default assignment
        for idx in range(self.num_mshr):
            m.d.comb += [
                req_arr[idx].valid.eq(0),
                req_arr[idx].addr.eq(0),
                req_arr[idx].way.eq(0),
                req_arr[idx].ftq_idx.eq(0),
                complete_arr[idx].eq(0),
            ]

        for ridx in range(2):
            # Allocate
            with m.If(self.ifill_req[ridx].valid & ready_enc.valid[ridx]):
                mshr_idx = ready_enc.o[ridx]
                m.d.comb += [
                    req_arr[mshr_idx].valid.eq(self.ifill_req[ridx].valid),
                    req_arr[mshr_idx].addr.eq(self.ifill_req[ridx].addr),
                    req_arr[mshr_idx].way.eq(self.ifill_req[ridx].way),
                    req_arr[mshr_idx].ftq_idx.eq(self.ifill_req[ridx].ftq_idx),
                ]
            # Complete
            with m.If(complete_enc.valid[ridx]):
                mshr_idx = complete_enc.o[ridx]
                m.d.comb += [
                    complete_arr[mshr_idx].eq(1),
                    self.ifill_resp[ridx].valid.eq(resp_arr[mshr_idx].valid),
                    self.ifill_resp[ridx].ftq_idx.eq(resp_arr[mshr_idx].ftq_idx),
                ]

        return m


class L1IFillUnit(Component):
    """ Logic for moving bytes from remote memory into the L1I cache.

    The L1I fill unit tracks outstanding cache misses until data has been 
    written back to the L1I data/tag arrays. Each pending miss is held in 
    an MSHR until L1I writeback is complete. 

    Handling multiple misses in parallel allows misses generated by prefetch 
    requests to begin/complete without blocking for misses generated by demand 
    fetch requests. 

    The :class:`L1IMshrArbiter` forwards fill requests to an available MSHR. 

    Ports
    =====
    sts: 
        Fill unit status driven [upstream] to instruction fetch logic
    l1i_wp: 
        L1I cache write port[s]
    req: 
        Fill request from instruction fetch logic
    resp: 
        Response to the FTQ
    fakeram: 
        Interface[s] to a mock RAM device

    """
    def __init__(self, param: EmberParams):
        self.p = param
        num_mshr = param.l1i.fill.num_mshr
        signature = Signature({
            "sts":     Out(L1IFillStatus(param)),
            "l1i_wp":  Out(L1ICacheWritePort(param)).array(num_mshr),
            "req":      In(L1IFillRequest(param)).array(2),
            "resp":    Out(L1IFillResponse(param)).array(2),
            "fakeram": Out(FakeRamInterface(param.l1i.line_depth)).array(num_mshr),
        })
        super().__init__(signature)

    def elaborate(self, platform):
        m = Module()

        # Instantiate a set of MSHRs
        mshr = []
        for idx in range(self.p.l1i.fill.num_mshr):
            x = m.submodules[f"mshr{idx}"] = L1IMissStatusHoldingRegister(self.p)
            mshr.append(x)

        # Instantiate the arbiter
        arb = m.submodules.arb = L1IMshrArbiter(
            self.p, 
            width=2, 
            num_mshr=self.p.l1i.fill.num_mshr,
        )

        # Connect MSHRs to the arbiter
        connect(m, arb.ifill_req[0], flipped(self.req[0]))
        connect(m, arb.ifill_req[1], flipped(self.req[1]))
        connect(m, arb.ifill_resp[0], flipped(self.resp[0]))
        connect(m, arb.ifill_resp[1], flipped(self.resp[1]))

        # FIXME: Each MSHR has its own L1I write port and memory interface? 
        for idx in range(self.p.l1i.fill.num_mshr):
            m.d.comb += arb.mshr_ready[idx].eq(mshr[idx].ready)
            m.d.comb += mshr[idx].complete.eq(arb.mshr_complete[idx])
            connect(m, mshr[idx].req, arb.mshr_req[idx])
            connect(m, mshr[idx].resp, arb.mshr_resp[idx])
            connect(m, mshr[idx].l1i_wp, flipped(self.l1i_wp[idx]))
            connect(m, mshr[idx].fakeram, flipped(self.fakeram[idx]))

        m.d.comb += self.sts.ready.eq(arb.ready)

        #mshr_ready = Array(
        #    Signal(name=f"mshr{idx}_ready") 
        #    for idx in range(self.p.l1i.fill.num_mshr)
        #)
        #m.d.comb += [
        #    mshr_ready[idx].eq(mshr[idx].ready)
        #    for idx in range(self.p.l1i.fill.num_mshr)
        #]

        #ready_encoder = m.submodules.ready_encoder = \
        #        EmberPriorityEncoder(self.p.l1i.fill.num_mshr)
        #m.d.comb += [
        #    ready_encoder.i.eq(Cat(*mshr_ready)),
        #]

        #r_mshr_alloc_idx = Signal(exact_log2(self.p.l1i.fill.num_mshr), init=0)
        #r_mshr_alloc_mask = Signal(self.p.l1i.fill.num_mshr, init=1)
        #r_mshr_alloc_ok  = Signal(init=1)

        #next_mshr_alloc_idx   = ready_encoder.o
        #next_mshr_alloc_mask  = ready_encoder.mask
        #next_mshr_alloc_valid = ready_encoder.valid

        #for idx, this_mshr in enumerate(mshr):
        #    alloc_ok = (
        #        self.req.valid & r_mshr_alloc_ok & (r_mshr_alloc_idx == idx)
        #    )
        #    with m.If(alloc_ok):
        #        m.d.comb += this_mshr.req.valid.eq(self.req.valid)
        #        m.d.comb += this_mshr.req.addr.eq(self.req.addr)
        #        m.d.comb += this_mshr.req.way.eq(self.req.way)
        #        m.d.comb += this_mshr.req.ftq_idx.eq(self.req.ftq_idx)

        

        # FIXME: mshr.data is unconnected; forwarding to IFU? 
        # FIXME: Actually allocate MSHRs; this design only supports one
        # FIXME: Arbitrate between available memory interfaces? - this design
        #        only supports one
        #connect(m, mshr[0].req, flipped(self.req))
        #connect(m, mshr[0].l1i_wp, flipped(self.l1i_wp))
        #connect(m, mshr[0].fakeram, flipped(self.fakeram))
        #connect(m, mshr[0].resp, flipped(self.resp))

        #m.d.comb += self.sts.ready.eq(Cat(*mshr_ready).any())

        return m








from amaranth import *
from amaranth.lib.wiring import *
from amaranth.lib.data import *
from amaranth.utils import ceil_log2, exact_log2

from ember.common.coding import ChainedPriorityEncoder


class SimpleCrossbar(Component):
    """ M-to-N crossbar (dubious implementation). 

    Given a set of "upstream" signals and "downstream" signals, map the index
    of each enabled "downstream" signal to the index of an enabled "upstream"
    signal.

    Ports
    =====
    upstream_grant:
        Bitvector of `num_upstream` upstream signals.
    downstream_grant:
        Bitvector of `num_downstream` downstream signals.
    dst_idx:
        Array of indexes to downstream signals mapped to each upstream signal.
        An entry is valid only when the corresponding `grant` signal is high. 
        An entry is set to zero when no mapping exists.
    grant:
        Valid bits for each mapping. 
        
    """
    def __init__(self, num_upstream: int, num_downstream: int):
        self.num_upstream = num_upstream
        self.num_downstream = num_downstream
        super().__init__({
            "upstream_grant": In(num_upstream),
            "downstream_grant": In(num_downstream),
            "dst_idx": Out(ceil_log2(num_downstream)).array(num_upstream),
            "grant": Out(1).array(num_upstream),
        })
    def elaborate(self, platform):
        m = Module()

        # Intermediate wires for outputs
        #
        # NOTE: These wires are only necessary because Amaranth doesn't seem 
        # to let you index into `Signature` array members with a `Signal`?
        grant_out = Array(Signal() for _ in range(self.num_upstream))
        dst_idx_out = Array(
            Signal(ceil_log2(self.num_downstream)) 
            for _ in range(self.num_upstream)
        )

        # Encoder selecting [up to] 'num_upstream' destinations
        down_enc = m.submodules.down_enc = \
                ChainedPriorityEncoder(self.num_downstream, self.num_upstream)
        m.d.comb += down_enc.i.eq(self.downstream_grant)

        # Encoder selecting [up to] 'num_upstream' distinct sources
        up_enc = m.submodules.up_enc = \
                ChainedPriorityEncoder(self.num_upstream, self.num_upstream)
        m.d.comb += up_enc.i.eq(self.upstream_grant)

        # Try to associate each enabled upstream signal to an enabled 
        # downstream signal.
        slot_grant = Array(Signal() for _ in range(self.num_upstream))
        slot_src = Array(
            Signal(ceil_log2(self.num_upstream)) 
            for _ in range(self.num_upstream)
        )
        slot_dst = Array(
            Signal(ceil_log2(self.num_downstream)) 
            for _ in range(self.num_upstream)
        )
        for slot_idx in range(self.num_upstream):
            grant = (down_enc.valid[slot_idx] & up_enc.valid[slot_idx])
            m.d.comb += [
                slot_grant[slot_idx].eq(grant),
                slot_src[slot_idx].eq(Mux(grant, up_enc.o[slot_idx], 0)),
                slot_dst[slot_idx].eq(Mux(grant, down_enc.o[slot_idx], 0)),
            ]

        # Default assignment for outputs
        for upstream_idx in range(self.num_upstream):
            m.d.comb += [
                grant_out[upstream_idx].eq(0),
                dst_idx_out[upstream_idx].eq(0),
                #self.grant[upstream_idx].eq(0),
                #self.dst_idx[upstream_idx].eq(0),
            ]

        # Map slots onto the output
        for slot_idx in range(self.num_upstream):
            src = slot_src[slot_idx]
            dst = slot_dst[slot_idx]
            # NOTE: This blocking assignment *should* give the desired behavior?
            with m.If(slot_grant[slot_idx]):
                m.d.comb += [
                    dst_idx_out[src].eq(dst),
                    grant_out[src].eq(1),
                ]
        for upstream_idx in range(self.num_upstream):
            m.d.comb += [
                self.dst_idx[upstream_idx].eq(dst_idx_out[upstream_idx]), 
                self.grant[upstream_idx].eq(grant_out[upstream_idx]), 
            ]

        return m




Supported Instructions
======================

In the Ember core, the set of supported instructions is ultimately defined by: 

- Including an :class:`RvInstGroup` within :class:`EmberParams`
- Including an :class:`EmberMopGroup` within :class:`EmberParams`
- A decoder module that maps each :class:`RvInst` to an :class:`EmberMop`
- One or more modules that decompose :class:`EmberMop` into micro-ops 

Defining RISC-V Instructions
----------------------------

RISC-V instructions are described by an :class:`RvInst`, which is used to 
generate a bitmask for uniquely identifying the instruction. 
A set of RISC-V instructions is organized into a :class:`RvInstGroup`. 

Defining Macro-Ops
------------------

In the Ember core, each :class:`RvInst` must be associated with
a "macro-op" (:class:`EmberMop`) which describes a set of control signals 
that will be carried down the instruction pipeline until dispatch.

The set of all macro-ops supported by the core is defined by an 
:class:`EmberMopGroup`, and must match the associated :class:`RvInstGroup`. 

After dispatch, macro-ops are converted into a "micro-op" representation 
which is specific to a particular pipeline in the backend. 

Defining Micro-Ops
------------------

.. warning::
   TODO



--------

.. automodule:: ember.riscv.inst
   :members:


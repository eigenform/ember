Return Address Predictor
========================

The **return address predictor** (RAP) is a memory device used to [speculatively]
track the value of a register (the **link register**) which links the target 
of a return instruction to the most-recent previous call instruction. 

In the RISC-V ISA, call and return instructions are implemented by expecting 
the programmer to use particular encodings of ``JAL`` and ``JALR``.
Software is responsible for using the general-purpose registers to link a pair 
of call and return instructions. The RISC-V ISA suggests that registers 
``x1`` and ``x5`` should be used as link registers, and that implementations
can use this as a way to distinguish the intent of ``JAL`` and ``JALR`` 
instructions. 

1. When we encounter a call, save the return address somewhere
2. When we encounter a return, predict with the most-recent previous 
   return address

.. automodule:: ember.bp.rap
   :members:



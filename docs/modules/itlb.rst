L1 Instruction Cache TLB
========================

The Ember core includes an L1I cache which is virtually-indexed and 
physically-tagged (VIPT). 
This means that the physical address associated with the requested cacheline 
must be resolved in order to determine whether or not it is present in any of 
the L1I cache ways. 

The L1I translation lookaside buffer (TLB) is a small cache for page table 
entries which is accessed in parallel with the L1I cache's tag and data arrays. 
When the L1I TLB is able to provide a physical page number, L1I tag matching 
and way selection can proceed without any additional latency. Otherwise, 
TLB misses must invoke the hardware page table walker (PTW) and cause the 
L1I cache access to incur substantial latency. 

--------

.. automodule:: ember.cache.itlb
   :members:


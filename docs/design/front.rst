.. include:: ../terms.rst

Front-End
=========

In the front-end of the machine, the ultimate goal is to keep a continuous
stream of [relevant] instruction bytes moving into the instruction pipeline.
At a high-level, this involves the following:

- Determining where [in memory] the instruction stream will continue
- Buffering requests to fetch instructions from somewhere in memory
- Prefetching bytes from some remote memory into the L1I cache
- Fetching instructions from the L1I cache
- Buffering fetched instructions for service downstream in the pipeline

.. warning::
   In modern computers, an L1I cache is typically supported by a hierarchy 
   of larger memories that are further away from the core (ie. a mid-level
   cache, a last-level cache, a DRAM device, etc). 

   For now, we're simply *assuming* that the next level in the memory hierarchy
   is actually robust enough to support all of this. 
   At this point, we're only relying on intentionally-simplified *models* of 
   memory beyond the first-level caches. 


.. glossary::

   Control-flow Request
    A request to continue the instruction stream at some location in memory.

   Cacheline
    The smallest addressible piece of data in a cache.

   Fetch Block
    A block of one or more sequential cachelines. 

   Fetch Target Queue
    A queue used to track a control-flow request until they can be serviced
    by instruction fetch. 

   
 


Control-flow Requests
---------------------

A **control-flow request** is an injunction to begin fetching instruction
bytes at some location in memory where the instruction stream should continue. 
Each request corresponds to a **fetch block**: a region in memory containing
the next fragment of the instruction stream. This is defined by:

- A program counter value, which gives the address of the first cacheline and 
  the offset to the first relevant instruction within the cacheline

- A number of sequential cachelines proceeding the initial block

.. note::
    Ideally, this also includes the offset of the last relevant instruction 
    within in the last cacheline.

This information is used to drive the front-end until the request is complete,
or until the request is cancelled and replaced.

A **control-flow control unit** (CFC) collects requests from different points
in the machine and controls how they are inserted into the front-end. 
Control-flow requests may be generated from various places in the pipeline, 
and may either be **architectural** or **speculative**:

- Speculative requests represent the *predicted* next fragment of the 
  instruction stream. 

- Architectural requests represent the next fragment of the instruction stream
  where the first instruction is guaranteed to be architecturally correct. 
  These must be serviced immediately, and must result in the entire pipeline 
  being invalidated. 

.. note::
   A fetch block is related to [but distinct from] the idea of a "basic block,"
   which comes up often in program analysis and compiler design. 

   - A fetch block can contain multiple basic blocks if the implementation
     can "squash" control-flow instructions that do not exit the fetch block

   - A fetch block can correspond to a single basic block if the last 
     instruction is the only control-flow instruction

   - A fetch block can correspond to a fragment of a basic block in cases 
     where the size of a basic block exceeds the size of a fetch block 
     defined by the implementation



Decoupling
----------

A **fetch target queue** (FTQ) holds control-flow requests until they can be 
serviced by the L1I cache. 

When an FTQ entry becomes the oldest in the queue, it is used to control 
the behavior of the demand fetch pipeline. This amounts to performing 
sequential L1I cache accesses until the pipeline stalls, or until all 
fetch blocks associated with the FTQ entry have been fetched successfully. 

The prefetcher selects pending entries from the FTQ in an attempt to
guarantee that the associated line is resident in the L1I cache 
before they reach the top of the queue. 

Misses in the L1I cache incur latency and inject bubbles downstream into the 
pipeline. In order to mitigate this, the front-end of the machine is 
allowed to "run ahead" of the rest of the pipeline in an attempt to 
pre-emptively fill the L1I cache with relevant bytes.

In principle, this is accomplished by taking advantage of the following facts:

- We can often pre-emptively compute the targets of control-flow instructions 
  shortly after retrieving them from memory (ie. in cases where the target can 
  be computed by adding the program counter to an immediate value)

- We can often predict the outcomes and/or targets of control-flow instructions
  ahead of time with reasonable accuracy

- We can pre-emptively start moving ("prefetching") bytes from memory into the 
  L1I cache as soon as the target of a control-flow instruction is known

.. note::
    This strategy is called "fetch-directed prefetching" (FDP).

L1 Instruction Cache
--------------------

All instruction bytes entering the midcore/back-end are fetched from the 
L1I cache. 

Organization
^^^^^^^^^^^^

The L1I cache is set-associative, and organized into two arrays:

- An array of tags (N sets, M ways per set, one tag per way)
- An array of cachelines (N sets, M ways per set, one cacheline per way)

The L1I cache is used in the "virtually-indexed and physically-tagged" (VIPT)
scheme. In a VIPT cache, address translation is not required to select a set.
However, the physical address must still be resolved in order to determine the 
existence of a matching way in the set. 

In general, accesses on the L1I cache take the following form: 

1. Start with a virtual address 
2. Resolve the physical address for the given virtual address
3. Compute a set index using the virtual address bits
4. Compute a tag using the physical address bits
5. Use the set index to read tags/data for all ways in a particular set
6. The way with the matching tag contains the cached data for the given 
   virtual address

Replacement Policy
^^^^^^^^^^^^^^^^^^

For now, the replacement policy is random. When an L1I cache write port is
used to write into a set, an LFSR randomly selects a way in the set that
will be replaced. 

Address Translation
^^^^^^^^^^^^^^^^^^^

In an attempt to avoid the latency associated with address translation in 
VIPT schemes, a translation lookaside buffer (TLB) is typically accessed in 
parallel with L1I cache data and tags. The TLB is a small, fully-associative 
memory that stores recently-observed page table entries. 

In the best case, a TLB hit allows tag matching to proceed immediately.
Otherwise, when a TLB miss occurs, we must wait for address translation.


Demand Fetch Pipeline
---------------------

The **demand fetch pipeline** used to retrieve data from the cache and send
it down the rest of the instruction pipeline. 

A **demand fetch request** indicates that the pipeline should begin reading 
a fetch block (consisting of one or more sequential cachelines).
This occurs when an FTQ entry becomes the oldest in the queue. 

Internally, each demand request yields one or more **fetch block requests**
which are passed down the pipeline [to the L1I cache] on proceeding cycles.

- Stage 0. Setup

  - When the pipeline is idle, accept a new demand request and send the 
    first request to stage 1
  - When the demand request is complete, change to the idle state
  - When the pipeline is running, increment the virtual address and 
    send the next request to stage 1
  - When stage 2 is stalled, wait for a response from the L1I fill unit
    before continuing the transaction

- Stage 1. L1I/TLB Access

  - Access the TLB and send the results to stage 2
  - Access the L1I data array and send the results to stage 2
  - Access the L1I tag array and send the results to stage 2

- Stage 2. Way select

  - If a TLB miss occurs, send a request to TLB fill/PTW and stall
  - If a tag miss occurs, send a request to the L1I fill unit and stall
  - If a tag hit occurs, send the result to predecode and the 
    decode buffer

Prefetch Pipeline
-----------------

TODO


Branch Prediction
-----------------

The front-end always fetches instructions in the order presented by the 
program. This is complicated by the following facts: 

- Pipelining necessarily involves latency
- Control-flow may depend on data (the architectural state)

Since many branches and jumps must be resolved during runtime, 
their exact effects cannot be definitively known until they have passed all
the way through the back-end of the machine (which may take many cycles). 
This means that the front-end cannot always know the precise order of the 
program in the immediate future. 

To mitigate this, control-flow must be *predicted* as early as possible.
Otherwise, we cannot deliver an uninterrupted stream of instructions to 
the rest of the machine. 

Control-flow is predicted in three fundamentally different but related ways: 

1. We can predict *the existence* of a control-flow instruction within a 
   particular cacheline. 

2. We can predict *the direction* of a conditional branch instruction. 

3. We can predict *the target address* of a control-flow instruction. 

L0 Predictions
^^^^^^^^^^^^^^

The L0 predictors use the program counter value (and information about the 
associated fetch block) to immediately predict the next program counter value.

This amounts to predicting *the existence* of an impending control-flow 
instruction within the block **and** predicting *the target address* of that 
instruction. Otherwise, if no control-flow instruction exists in the block, 
the next effective program counter value is assumed to be the address of the 
next-sequential fetch block. 

.. note::
    We can also imagine cases where a stream of many fetch blocks can be 
    predicted ahead-of-time solely based on the program counter value. 
    By keeping track of how basic blocks are split into fetch blocks, 
    you should be able to determine *sequences* of impending fetch blocks
    ahead-of-time instead of the strategy described here (predicting the 
    stream on a block-by-block basis). 


L0 prediction ensures that a new control-flow request is fed back into the CFC 
each cycle, allowing us to avoid inserting bubbles into the pipeline. 

This is mainly supported by the **L0 branch target buffer (BTB)**: a 
fully-associative storage whose entries correspond to predecoded L1I 
cachelines which contain:

- At least one *unconditionally-taken* control-flow instruction
- At least one *conditional, biased-taken* control-flow instruction

A match in the L0 BTB indicates that the address of the next-fetch cacheline 
is known with very high confidence. 
Relative to other predictors, storage must be small in order to support 
accesses that will complete within a single cycle.

.. note::
    Intuitively, it seems like the following situations can be ("should be able 
    to be") trivially predicted with no latency: 

    1. If the fetch block for the program counter is terminated by an unconditional 
       jump/call, use the cached target address
    2. If the fetch block for this program counter is terminated by a return 
       instruction, use the L0 RAP 
    3. If the fetch block for this program counter is terminated by a *biased-taken*
       conditional branch, use the cached target address

    The strategy for determining which control-flow instruction to use is: 

    1. Find the cacheline in an fully-associative storage
    2. Go to the offset of the entrypoint into the fetch block
    3. Select the first instruction which is unconditionally-taken or predicted-taken
       
    3. Invoke the appropriate L0 predictor
    4. If no instruction is predicted-taken, predict the next-sequential block


Instruction Predecode
---------------------

The predecoders identify control-flow instructions and extract immediates from 
words shortly after a block has been prefetched into the L1I cache. 

Each predecoder has a full 32-bit adder which computes the target addresses 
for direct branch and jump instructions. 



The predecode unit sends this information to the branch prediction unit, 
where it can be used to generate


Predecoding allows us the following: 

1. We can discover unconditionally-taken control-flow instructions (and their 
   target addresses) immediately after a cacheline has been fetched. 
   This allows us to quickly obtain the next cacheline that must be fetched. 

2. We can discover conditional control-flow instructions immediately after
   a cacheline has been fetched. This allows us to begin predicting the
   branch direction early in the pipeline. 

.. note::
   Ideally, predecoding occurs immediately after prefetching. 



The next-sequential fetch block can be predicted when the following conditions
are met (and ideally, recognized as early as possible in the pipeline):

- There are no control-flow instructions in the predecoded block
- There are no serializing instructions in the predecoded block
- There are no illegal instructions in the predecoded block

When a predecoded fetch block has a single control-flow instruction, the data
is sent to the appropriate predictor: 

- Since the target addresses of unconditional direct jumps/calls are computed 
  by predecoders, the target address can be used without additional latency 
- Conditional branches are sent to the appropriate direction predictor
- Indirect jumps/calls are sent to the appropriate target predictor


.. note::
    When a predecoded fetch block contains more than one control-flow 
    instruction, we need to make a decision about which instruction should 
    be used to predict control-flow. 




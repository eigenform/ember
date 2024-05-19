Fetch Target Queue
==================

The **fetch target queue** (FTQ) is responsible for tracking all outstanding 
requests for instruction fetch. 

1. Fetch requests that result in an L1I miss or TLB miss can be parked and 
   subsequently replayed after the associated L1I fill or PTW request has 
   been completed. This effectively makes many interactions with the L1I 
   non-blocking.



.. automodule:: ember.front.ftq
   :members:


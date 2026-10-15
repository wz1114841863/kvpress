# RTL3.9-C4-A — eligible page-free event capture

## Status

C4-A is complete for the only newly eligible R5 event: `page_free`. The
precondition audit found that terminal and retire acknowledgement were already
bound by C4-P2, and that descriptor-invalidate cannot be captured under the
same-carrier field rule. The exact mapping is
[`rtl3_9_c4_a_eligible_event_capture_manifest.json`](rtl3_9_c4_a_eligible_event_capture_manifest.json).

## Binding

`RouteAPageFreeScoreboardObserver` is a zero-buffer testbench observer at
R5's actual `allocator_release_out` handshake. It copies only the old
`PageRef` and requires the observed release output and the page-free event to
fire atomically. Event-ready low therefore holds the actual R5 release
observation and cannot create an event or free a page. It deliberately does
not redefine R5's already owner-local `reclaim_complete`, which may be high
before that post-durability observation is accepted.

The C3b directed witness stalls the event after the matching outer functional
descriptor terminal, checks old page id/generation while the event is held,
then releases the event before observing the existing R6 retire ack. It also
checks that the R5 post-durability observation does not redefine
`reclaim_complete`. This is an event/carrier witness, not an HBM or SRAM
controller model.

`descriptor_invalidate` remains excluded. Its schema operation/context fields
are not present on `allocator_release_out`; neither a descriptor line,
historical adapter constant, outer response, nor `reclaim_complete` may fill
them in.

## Next phase

C4-B may now replay the accepted C4-A event trace through success and bounded
legal backpressure. C4-C retains stale/mismatch, numeric-fault, and reset
coverage. C4-D remains the validation and bounded functional-subsystem review
phase. No physical, PPA, timing, throughput, numeric, model/GPU, or complete
inference claim is made.

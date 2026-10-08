# RTL2.6.5a.1 — actual packed-S2 read composition

**Status:** `implemented_test_only_actual_packed_read_subpath`.

This first RTL2.6.5 read-path sub-slice replaces direct S2 payload injection
with the existing typed packed read path in one Chisel harness:

```text
verification PackedS2ReadWork + S2 service association
  -> R2/R1 read request
  -> matching 8-fragment external response
  -> typed packed-S2 endpoint
  -> S2 payload + sidecar completion / READY
  -> four consumer commits / release / R6 merge / R4-R6 fault terminal
```

The test drives the existing `PackedS2ReadWork` as explicit verification
ingress, but it no longer injects S2 payload fragments. The R1 response is
identity-checked and the typed endpoint owns the S2 fill. S2 sidecar facts
remain explicit verification ingress because sidecar/page-management
realization is not selected here.

This is no-model, no-GPU, no-timing/PPA functional-control evidence. It is not
a production packed-read scheduler, R3/R5-to-work bridge, complete
publication-to-terminal witness, or full RTL2.6.5a closure. RTL2.6.5a.2 must
compose the existing R3 `pack_read -> R2/R1 -> P3` path into the retained
witness and test its stale/mismatch/fault non-deposit behavior.

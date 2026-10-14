# RTL3.9-B3 — atomic publication and authority functional closure

**Status:** `complete_functional_atomic_publication_authority_closure`.

RTL3.9-B3 closes the existing atomic-publication sequence in one functional
Chisel instance.  It extends, but does not revise, the B0 association contract
or the B1/B2 payload and descriptor durability paths:

```text
R3 payload durable + R5 descriptor durable
  -> R3 M2 group-member request/response (two required members)
  -> R3 sole publication candidate -> M2 publication request
  -> R3 visibility apply -> R5 matching visibility acknowledgement
  -> R3 sole metadata-publication acknowledgement/linearization
  -> R3 post-commit observation + R6 pending -> packed authority acceptance
```

## Owner and commit boundary

- **R3** remains the sole owner of the staged page/tag/generation association,
  M2 member protocol, publication candidacy, `metadata_publish_commit`, and
  the resulting authority transition.
- **R5** remains the sole owner of descriptor visibility.  Its acknowledgement
  is a prerequisite to R3's publish acknowledgement; it does not issue M2
  publication or authority state.
- **R6** accepts and records the already-committed R3 `pending -> packed`
  authority fact.  It observes the completed publication acknowledgement but
  neither creates a second commit nor owns publication membership.
- The M2 reference protocol provider is functional and replaceable.  It is
  neither an SRAM macro nor a latency, port-count, bandwidth, or energy model.
- The production top remains composition-only.  B3's harness uses the same
  R3-to-R5/R6 protocol directions; it does not add a top-level scheduler,
  fallback path, or testbench-generated authority event.

The B3 directed witness starts from RTL3.9-A's R3 materializer feedback,
drives the real B1 packed-write and B2 descriptor-durability path, and then
uses the existing M2 provider/R5/R6 interfaces.  It proves that each required
M2 member round trip occurs, R5 accepts the visibility application, R3 accepts
the matching `Published` acknowledgement, and only then R6 accepts the exact
entry-0 `pending -> packed` authority transition.  Holding the post-commit
publication observation under ready-low does not re-run publication.

## Exactness and failure boundary

Publication cannot become visible from payload durability alone, descriptor
durability alone, an unmatched M2 response, or a visibility acknowledgement
without an active matching R3 publication.  Those fail-closed checks remain in
the existing R3/R5 protocol owners and their directed tests.  B3 does not
weaken stale identity, generation, member, page-reference, or status matching.

An initially observed B3 timeout was diagnosed as a harness-only repeated
legacy `publication_ack` connection.  The automatic path had already reached
R3 ack-valid and R6 ack-ready, but that old direct connection reintroduced the
legacy testbench ready.  Removing the duplicate connection restores the
single mode-selected sink; no R3/R5/R6 protocol semantics changed.

## Explicit exclusions

This closure selects no HBM controller, SRAM macro, M2 physical organization,
port count, clock/CDC, latency, throughput, bandwidth, area, energy, PPA,
numeric datapath, model/GPU run, or new A4 DSE.  It does not reopen pruning,
admission, page size, P3 mapping, S2 count, GQA legality, queue/scheduler
semantics, or the single atomic-commit boundary.

## No-model validation

### Historical source provenance

The immutable B3 manifest remains byte-for-byte unchanged.  Its
`source_sha256` values name the B3 source snapshot at
`c5ccda66651ac71abe790861f6a3cc0f611c7333`, recorded in
[`rtl3_9_b3_atomic_publication_authority_historical_provenance.json`](rtl3_9_b3_atomic_publication_authority_historical_provenance.json).
The validator replays those hashes through `git show` at that commit and also
requires that commit to remain an ancestor of `HEAD`.  It deliberately does
not hash mutable descendant live files: C0 legitimately extends the R3/top
interfaces and the living phase ledger, and must be validated by its own
contract.  Historical B3 replay therefore proves neither C0/C1 behavior nor
current physical implementation.

```bash
.venv/bin/python tools/validate_rtl3_9_b3_atomic_publication_authority_activation.py --help
.venv/bin/python tools/validate_rtl3_9_b3_atomic_publication_authority_activation.py
.venv/bin/pytest -q tests/test_rtl3_9_b3_atomic_publication_authority_activation.py
cd hardware/route_a/chisel
sbt -batch 'Test / compile'
sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265a2PackReadPublicationSpec -- -z "closes automatic M2 publication"'
```

The selected Chisel/Verilator witness passed on 2026-10-13 with one test, zero
failures, and zero errors.  This is pure functional control/dataflow evidence;
it is not a latency, throughput, physical-memory, numeric, RTL-completeness,
or PPA claim.

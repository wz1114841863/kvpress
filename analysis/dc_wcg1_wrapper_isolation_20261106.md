# WCG1 optional real-wrapper integration and validation preparation

Status: candidate implemented, bounded compile and gate-model checks pass;
real-wrapper functional regression is prepared, not yet accepted.
Authorization: run RD1+PM1 full paired DC independently while starting WCG1
wrapper isolation; preserve 2 ns, function, concurrency and handshakes;
exclude RD2. The RD1+PM1 archive was frozen before these source edits.

## Candidate implementation

`RouteAM2P3Wrapper(p, gateCompactMembershipWords = false)` retains its default
realization. Only explicit test/candidate instantiations select true; production
tops remain false. This constructor option adds no external port or handshake.

The candidate replaces each unreset member/suffix word with an unreset word
register behind its own low-phase-latched clock gate. There are still all
36 x 64 entries and all typed fields; member width is 79, suffix width remains
parameter-derived (80 at the synthesis anchor). The two exact write enables
are `admission_context_in.fire` and that same fire AND binding-offered.
Bank and ordinal decoding preserve the old write indexing; no reset mask,
new ready predicate, valid gating or pipeline stage is introduced.

All presence masks, stage controls, reconciliation journal, RD1 M/S/O reader,
C/F/B reads, suffix reads, materializer and publication logic stay on their
existing paths. Source guards confirm unchanged join-ready assignments and
other production owners. No ST1 journal reuse or RD2 reader is selected.

`RouteACompactWordClocking` contains the candidate helper. Its inline primitive
uses the previously screened CKLNQD1 native library cell under SYNTHESIS;
ordinary simulation uses a transparent-low latch and full-pulse AND output.
The native gate's internal latch is a real hardware cost, not removed state.
Simulation is unsdf and does not establish setup/hold timing. A full source
freeze must include the inline `.sv` file before any later synthesis; the
existing RD1+PM1 full DC does not consume these files.

## Verification implemented

- Bounded local `Test / compile` passes with 2-GiB JVM heap and two processors;
  no local full C++ simulator build is launched.
- The **actual inline source** extracted from the Scala helper is compared
  against the pinned native CKLNQ functional model with Icarus. Simulation
  and SYNTHESIS bindings each pass 240 checks, including late-low enabling
  and high-phase enable changes with full-pulse edge assertions. The vendor
  model SHA remains `4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf`.
- The real `RouteARTL39AMaterializationHarness` optionally instantiates both
  candidate and reference wrappers. Every input/ready-backpressure leaf is
  shared, output valid/ready is compared continuously, and payloads are
  compared whenever their owning Valid/Decoupled channel is live. Undefined
  inactive payload bits are not promoted to a new functional contract.
- The original three materialization/fault/packed-write/terminal tests are
  retained; an additional case covers unbound joins, missing-authority stalls,
  duplicate rejection, two banks reusing ordinal 63 and destructive reset.
  Candidate tests use 36 x 64 x (79+80) data geometry, including a high-bit
  64-bit pending handle; unrelated test-only allocator capacities stay small.
- Candidate `RouteAWCG1WrapperSpec` inherits these four tests with the full
  wrapper reference miter enabled. Baseline also runs all four, with its
  original narrower test memory-reference profile. Each is a matched test
  against its own parameter-equivalent reference, not a cross-profile area
  comparison. C++ compilation is limited to one build job/two Verilation jobs.

The local compile is not a functional PASS. The new remote runner must verify
both four-case XML reports, zero failures/errors/skips, all source hashes,
native test completion and outer exit 0. It launches no DC and performs no
new RTL emission/full paired synthesis. Its source archive explicitly excludes
the three unused RD2 helper/spec/emitter files. A new isolated workspace and
tmux keep it independent of the frozen RD1+PM1 synthesis.

## Open gates

This is directed differential simulation, not formal equivalence for every
legal generic trace. Full concurrency, reset/claim/reuse, unbound suffix
retention, invalid/stale input and publication/observation cases need their
explicit coverage review; the existing cell-bank unit supplies separate
known-word/raw-read evidence. No protocol concession is allowed to close a
test failure. Preserve failed diagnostics and revise the isolated candidate.

After functional acceptance, emit/check the real-wrapper isolated synthesis
boundary, all data bits, native gate binding and the inline-file closure.
Then measure actual parent-enable setup/hold and propagated capture clocks
at 2 ns using matched reference policy and accounted hold repair. Single-bank
hold margin was only 3.529 ps; no real-wrapper timing closure is assumed.
WCG1+RD1+PM1 complete paired DC is not started by this batch.

RD1+PM1 remains an independent full-area/timing measurement. Do not add its
eventual savings to the single-bank WCG1 saving arithmetically. No PPA,
external-service zero cost, physical signoff, speedup or hardware net benefit
is claimed here.

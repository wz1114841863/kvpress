# RTL2.0g — R4 verification-only result-stub provider

**Status:** r4_result_stub_interface_owner_closed; testbench_behavior_pending.

This closure binds the last RTL2.0 amendment: a testbench-only provider may
supply one deterministic success or numeric-fault fact through the already
frozen R4 result boundary. It is neither a numeric-core implementation nor a
source of architectural terminal outcomes. It does not activate a Chisel
provider, create an R4 datapath, change R4 packet behavior, or establish
timing, throughput, PPA, model/GPU, or new A4 DSE evidence.

The machine-readable record is
[rtl2_0g_r4_result_stub_provider_manifest.json](rtl2_0g_r4_result_stub_provider_manifest.json).

## Testbench-only ownership and binding

testbench_route_a_r4_result_stub_provider is a verification environment
endpoint. It observes one R6-produced, nonempty merge_req and binds exactly one
live test scenario outcome to that identity:

    R4StubScenario {
      transaction_identity, disposition={success,numeric_fault},
      normalized_value_4096b when success
    }

The provider must not infer an outcome from packet data, source order, payload,
or internal R4 state. Scenario selection is an explicit testbench input and
must be stable while held. The normalized value is opaque verification data:
the provider does not calculate, classify, normalize, round, or claim binary32
conformance for it.

Only after the matching merge_req is accepted by route_a_merge_boundary may the
provider offer exactly one mutually exclusive carrier:

    success       -> R4ResultStub(transaction_identity, normalized_value_4096b)
    numeric_fault -> R4NumericFault(transaction_identity)

It retains the selected fact until the R4 boundary accepts it, then retires
that testbench association. It cannot offer before merge_req, for an empty
source set, for a stale/reset identity, or more than once for the same accepted
merge request. It must never assert success and fault together.

## Exact terminal chain

    R6 accepted nonempty merge_req
      -> one testbench R4 success OR numeric-fault offer
      -> R4 boundary accepts and maps to merge_rsp_or_numeric_fault
      -> R6 is the only outward attention-terminal consumer

The provider does not consume source packets or ConsumerPartialCommit; it does
not create source release, merge request, lifecycle terminal, retry, fallback,
authority transition, publication, page operation, or retirement fact. A
numeric fault stays fail-closed: it has no normalized result, retry, Full-KV
substitution, admission/mask change, or terminal bypass.

## Stalls, reset, and exclusions

A ready-low R4 boundary can only delay an offer. While it is held valid, the
identity, selected disposition, and success value remain unchanged. A
destructive reset invalidates every live provider association; post-reset or
mismatched testbench scenarios are rejected without mutation. Eventual offer
after an accepted merge request is an environment fairness assumption for
bounded progress tests, never a latency or throughput claim.

This closure does not choose an exp implementation, precision, lane storage,
pipeline, source mux, source order equivalence, R4 numerical algorithm, or a
synthesizable RTL implementation. Its sole purpose is deterministic control
and terminal-path verification before a separately reviewed numeric realization.

## Validation

    .venv/bin/python tools/validate_rtl2_r4_result_stub_provider_manifest.py --help
    .venv/bin/python -m pytest tests/test_rtl2_r4_result_stub_provider_manifest.py -q

This is a pure-software executable testbench-interface contract: no model/GPU,
cycle/timing/throughput, PPA, RTL-correctness, numeric-datapath, or new A4 DSE
claim is made.

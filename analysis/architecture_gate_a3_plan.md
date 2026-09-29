# Gate-A3 plan — finite RTL-boundary parameter closure

## Status and authority

**Status:** A3 finite-profile closure complete.  The selected RTL-entry
anchor is `rtl_entry_qwen3_8b_32k_s1_v1`; it is not a Gate-A pass and does not
authorize RTL implementation.

The pre-selection plan snapshot remains byte-bound by
`analysis/architecture_gate_a3_plan_provenance.md`.  This refinement is
separately byte-bound by
`analysis/architecture_gate_a3_refinement_provenance_freeze.md`.

Gate-A3 follows the completed Gate-A2 pure-software semantic harness.  Its
purpose is to replace the remaining unbounded identities, address spaces, and
endpoint resources with a reviewable finite RTL-boundary profile.  It must not
run model/GPU workloads, perform a performance/energy/PPA DSE, modify A4 frozen
artifacts, or change the original mask, admission, M2 queue semantics, P3
mapping, S2 count, GQA legality, scheduler, or atomic publication boundary.

Gate-A3 completion means only that the finite **interface profile** has been
closed and validated against the A2 reference.  Gate A remains open pending
macro/controller realization, numeric datapath, common-clock/arbitration/
overlap closure, and final interface review.

### Implemented verification-only portion

The pure-software validator is `kvpress/route_a_rtl_profile.py`; the complete
small profile is `analysis/architecture_gate_a3_verification_small_v1.json`;
the selected entry profile is
`analysis/architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json`; the former
input template is retained at
`analysis/architecture_gate_a3_rtl_entry_qwen3_8b_v1_input_template.md` as
decision/provenance navigation; and the directed tests are
`tests/test_route_a_rtl_profile.py`.  This portion implements profile-class
separation, checked finite namespace and capacity relations, allocator
generation/reuse safety, external logical retirement, and transport-endpoint
credit losslessness.  It is a pure-software interface contract, not RTL or
an implementation-performance result.

## Required profile separation

Every A3 manifest has an explicit `profile_class` and may not reuse values
across classes without an explicit review decision.

| Profile | Purpose | Parameter status |
|---|---|---|
| `verification_small_v1` | Small finite state space for exhaustive/randomized ID-wrap, stale-response, allocator-reuse, and backpressure tests | Verification-only values; never a deployment claim. |
| `rtl_entry_qwen3_8b_32k_s1_v1` | One Qwen3-8B Route-A anchor instantiation: 32K context and one concurrent sequence | Deployment assumptions/derived values; not a performance, capacity sufficiency, or portability claim. |

The verification profile's small `RID_W`, epoch, pool, or fragment values must
be marked `verification_only` at every serialization and report boundary.

## Deployment-envelope inputs

The entry profile selects deployment inputs by engineering review, not from
the three A4 workloads or their observed maxima.  Its field vocabulary is
syntactically a `retention_kv_semantic_interface_v1` profile, while its
evidence scope is explicitly only `route_a_qwen3_8b_anchor_only`; this does
not claim cross-algorithm portability.

```text
MAX_CONTEXT_TOKENS = 32768
MAX_CONCURRENT_SEQUENCES = 1
NUM_LAYERS = 36                 # Qwen3-8B anchor
NUM_KV_HEADS = 8                # Qwen3-8B anchor
MAX_PACKED_PAGE_POPULATION = 64 # frozen Route-A page limit
HOT_WINDOW_TOKENS = 128         # frozen Route-A semantic anchor
K_V_PAYLOAD_BYTES_PER_TOKEN = 512
POSITION_SIDECAR_BYTES_PER_TOKEN = 8
MAX_PENDING_RESIDENT_RECORDS = 9,400,320  # derived keep-all cold bound
MAX_LIVE_PENDING_TRANSACTIONS = 1
NUM_PENDING_ENDPOINTS = 1
NUM_PACK_ENGINES = 1
KV_HEAD_GROUP_PARALLELISM = 1
MAX_LIVE_READ_REQUESTS = 4       # 2 S2 fills + 1 endpoint + 1 pack read
MAX_LIVE_WRITE_REQUESTS = 1      # one pack write
MAX_LIVE_SOURCE_GROUPS = 1
CORE_DATA_W = 512 bits = 64 B fragment
TOTAL_COLD_KV_HBM_POOL_BYTES = 5 GiB
```

For every input, the manifest must name its owner as one of
`architecture_review_input`, `frozen_anchor`, or `derived`, and state its
units.  An `architecture_review_input` blocks A3 pass until a concrete value
is approved.  A `derived` value must carry a checked equation and referenced
inputs.  A bounded range is allowed only if all values have the same RTL
interface width and the manifest records the associated compile-time check.

`MAX_PENDING_RESIDENT_RECORDS` and `MAX_LIVE_PENDING_TRANSACTIONS` are
deliberately different.  The former is the authoritative pending-HBM
population bound; the latter is the one direct endpoint stream.  A full
pending backing may therefore cause only lossless backpressure, never a large
on-chip pending FIFO, a mask change, an admission change, or Full-KV fallback.
Neither field alters frozen `metadata_control_local32/shared256/staging512`,
M2 ownership, lossless queue/credit semantics, or the scheduler.

The 5-GiB `TOTAL_COLD_KV_HBM_POOL_BYTES` is one shared physical address pool
whose pending and packed allocations retain distinct authority/state tags.  It
is not two independently provisioned 5-GiB regions.  With all cold records
retained, the checked demand is:

```text
cold_records = (32768 - 128) * 1 * 36 * 8 = 9,400,320
packed_pages = 1 * 36 * 8 * ceil((32768 - 128) / 64) = 146,880
page_storage = 64 * (512 B + 8 B) = 33,280 B
required_pool = (146,880 + 1 migration page) * 33,280 B
              = 4,888,199,680 B
```

The one migration-page reserve covers the temporary pending-plus-new-packed
copy before atomic metadata publication.  The 5-GiB selection is a finite
address/capacity contract only; it makes no physical-HBM, controller, PPA, or
throughput claim.

## A3 closure items

### Transaction identity and lifetime

The A3 contract will retain A2's strict-no-reuse profile as a regression
baseline and select one RTL profile with globally unique transaction identity:

```text
transaction_identity = (rid, incarnation)
```

The manifest must specify `RID_W`, `INCARNATION_W`, `MAX_LIVE`, and a checked
namespace relation.  A live `rid` cannot acquire another incarnation.  Reuse
requires a new incarnation after exactly one terminal outcome.  Incarnation
wrap is legal only under an explicit quiescence predicate:

```text
no live request with the old rid/incarnation
no outstanding response that can carry the old identity
no S2 slot association carrying the old identity
no direct-pending endpoint association carrying the old identity
```

For the selected entry profile, `RID_W=3`, `INCARNATION_W=2`, and
`MAX_LIVE=6`; the checked six is `4 read + 1 write + 1 source-group` contract
count, not a service-rate claim.  The strict no-reuse A2 profile remains a
regression baseline.

### Page identity, allocation, and reclamation safety

The RTL-visible descriptor schema must close page/reference/handle/generation
widths from the selected packed HBM region and page capacity.  A3 must specify
the following safety lifecycle without inventing a request-retirement policy:

```text
allocate -> allocated_unpublished -> write_commit -> metadata_publish
        -> live_packed -> no_live_reference -> reclaim
        -> generation/validity advance -> reusable
```

The selected ownership is: the external runtime/session manager owns logical
retirement, while the KV subsystem owns drain, quiescence checks, physical
reclamation, and generation/validity advance.  Page-generation wrap requires
no old live page reference, response, S2 association, direct-endpoint
association, or metadata reference.  This freezes an interface ownership
boundary; it does not specify runtime cancellation, retry, or reclamation
timing policy.

### Credit and endpoint transient state

Two names remain distinct:

```text
metadata_control_credit     # frozen A4 M2 queue/credit semantics
transport_endpoint_credit   # A3 finite transport in-flight resource
```

`transport_endpoint_credit` must define only logical endpoint capacity,
reserve/release predicates, and lossless backpressure.  It is neither a
physical FIFO depth nor a reinterpretation of `local32/shared256/staging512`.

For `direct_pending_endpoint_v1`, the selected finite transient contract is
one record, eight live 64-B fragments, and eight transport credits; the
transport endpoint owns data while downstream is not ready and full capacity
only backpressures.  `CORE_DATA_W=512` bits is an engineering RTL-boundary
choice matching the 64-B fragment, not a numeric-datapath, timing, or
performance result.  The frozen 256-B accounting beat is not an RTL bus-width
assumption.

### S2, M2, faults, and clock wrapper

S2 remains exactly two common source slots with generation/validity and the
existing four-consumer release rule.  M2 preserves its frozen semantic
ownership/publication boundary.  The A3 wrapper may define abstract synchronous
`core_clk` sampling of ready/valid interfaces, but this is not an HBM clock,
controller, latency, arbitration, or overlap model.

Fault handling is fail-closed:

```text
terminal fault -> no authority transfer -> no dependent publish/consume
               -> no mask change -> no Full-KV fallback
               -> architectural error status propagates upward
```

Retry, recovery, timeout policy, physical controller behavior, and forward
progress after a terminal fault are explicitly outside A3.

## Planned executable artifacts and checks

1. A versioned JSON/YAML parameter manifest with schema validation and
   `profile_class` enforcement.
2. A pure-software profile validator extending the A2 reference; no model,
   trace, GPU, timing, or PPA input.
3. Deterministic and fixed-seed tests for finite ID/incarnation reuse and wrap,
   page generation/reuse preconditions, fragment/endpoint credit exhaustion,
   fault propagation, and legal stalls/interleavings.
4. A derived-value checker for every width/capacity equation and a rejection of
   unexplained A3-owned `TBD` values.
5. A provenance freeze that binds the plan, manifest, validator, tests, and
   exact no-model pytest command/result.

## A3 acceptance checklist

An A3 profile can be marked complete only when every A3-owned field is exactly
one of:

```text
fixed concrete value
derived value with a checked equation
bounded allowed range with an explicit RTL consequence
```

All A3-owned deployment inputs, `no_live_reference` ownership, endpoint
fragment width, and transport-credit bounds are concretely selected or checked
as derived values in `rtl_entry_qwen3_8b_32k_s1_v1`.  A3 completion still does
not pass Gate A or authorize RTL.

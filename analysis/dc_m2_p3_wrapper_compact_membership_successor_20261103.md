# M2/P3 compact-membership successor closure — 2026-11-03

## Scope

This record accepts the generated-source and paired typed-array-proxy gates
for compact-membership functional commit
`7bcd6526a941d62aabaaf59f99a31a9b5bc1c98a`.  It follows the 57/57 functional
pass in `dc_m2_p3_wrapper_compact_membership_implementation_20261103.md`.

This is generated logical-state and structural-input evidence.  It is not a
DC mapping, timing, lint, power, PPA, speedup, external-service-zero-cost, or
hardware net-benefit result.

## Immutable raw successor

The versioned remote root is:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  m2p3_compact_7bcd652_p9/
```

The retained generation log is
`m2p3_compact_p9_hdl_20261103.log`.  CHIRRTL emission, split firtool lowering,
R5 descriptor checking, the control-refinement source checker and the outer
runner all pass with `KVZAP_M2P3_COMPACT_P9_HDL_EXIT=0`.

| item | observed result |
| --- | ---: |
| split SystemVerilog files | 48 |
| aggregate SV bytes | 451,077,663 |
| ordered source-closure SHA-256 | `f7f0e84f25a59680e11c2240083e2e1c6378351620fb6ac276e058ca72d3a78e` |
| successor filelist SHA-256 | `5201ba412545e8f0017bd457a899e8caa9d06e9c27425e792eade5420471938d` |
| typed top-port families | 16/16 |
| retained non-black-box production owners | 12/12 |
| raw Route-A typed array interiors | 4/4 |
| excluded old R5 descriptor backing tokens | 0 present |

All external memory, R5 descriptor, sidecar, partial-source, R4 result/fault,
terminal and retire boundaries remain explicit.  This proves source presence
and owner retention, not their physical cost or timing.

## Compact wrapper state

The streaming generated-state checker observes:

| state scope | prior accepted successor | compact successor | delta |
| --- | ---: | ---: | ---: |
| all emitted modules | 13,733,895 | 13,144,071 | -589,824 |
| named array interiors | 1,475,124 | 1,475,124 | 0 |
| `route_a_m2_p3_wrapper` | 990,322 | 400,498 | -589,824 |
| `route_a_metadata_admission_bridge` | 17,492 | 17,492 | 0 |

The wrapper reduction is exactly 59.559%, matching the P0 source prediction.
The old member table declared eight per-record fields; the successor declares
only `logical_position` and `payload_ref`.  The old pending-binding table
declared fifteen fields; the successor retains only transaction identity,
payload handle, source generation and destination endpoint.  Repeated
`entry_id`, layer, head, logical/payload copies and group/M2 mapping fields are
absent from the new table declarations.

The 400,498-bit count is raw generated state.  It does not establish the P0
76,032-cell mapped-sequential ceiling or any mapped-area reduction.

## Paired proxy closure

The versioned paired artifacts are:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  m2p3_compact_7bcd652_p9_paired_input.tar.gz
  m2p3_compact_7bcd652_p9_dc_array_proxy_manifest.json
  m2p3_compact_7bcd652_p9_dc_array_proxy_r1/
```

The retained proxy log ends with
`KVZAP_M2P3_COMPACT_P9_PROXY_EXIT=0`.  The archive is 27,224,473 bytes with
SHA-256 `61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008`.
The manifest SHA-256 is
`de6cd6023138cba8974dd70aa043b864e1819db79cf04148c852108a38f98e6d`;
the independent proxy-check report SHA-256 is
`6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2`.

The paired filelists contain exactly one Full-KV source and 48 Route-A
sources.  All five approved same-header proxies pass:

1. Full-KV S2 payload;
2. Route-A M2 entry;
3. Route-A P3 stage;
4. Route-A R5 availability/generation;
5. Route-A S2 payload/sidecar.

The M2/P3, R5 page-manager and S2/GQA parent controls remain implemented and
non-black-box.  The manifest continues to classify external services as
nonzero and unestimated.

## Disposition

The compact-membership generated-source and paired-proxy gates pass.  Together
with the prior functional batch, this closes the bounded pre-DC successor
gate.  Any same-`dc_feasibility_fair_v1` paired DC comparison requires separate
authorization and a new immutable run ID; it must not relax the clock, enlarge
Full-KV, black-box parent control, or infer mapped/PPA benefit from these raw
state counts.

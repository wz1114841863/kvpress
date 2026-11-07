# RD1+WCG1 full paired DC — input-freeze failure inspection

Inspection date: 2026-11-07, Asia/Shanghai. Run:
`dc_feasibility_fair_rd1_wcg1_20261107_r1`.
Source snapshot: `fdb4dff` on `research/kvzap-latest`.

## Decision

**Contextual RTL export r2 completed, but the full pipeline failed in input
freeze before native binding or either formal synthesis side started. There
is no new mapped-area, setup, hold or fanout result.**

The failure is a preparation-script hash-domain mismatch, independently
reproduced from the frozen script/helper and actual exported file. It is not
a DC crash, timing failure, native-gate binding failure or demonstrated RTL
functional regression. Do not reinterpret the previous isolated-wrapper
15.624812% saving as a completed full-top result.

This inspection reads remote files, processes, markers, sources and hashes;
it runs no model, simulation, DC/STA or freeze main, and writes no remote
file. It does not restart, kill, retry or change any run. Other EDA work is
not touched. The old r1/r2 export and failed full-pipeline artifacts remain
intact. Evidence: [inspection JSON](dc_rd1_wcg1_full_paired_inspection_20261107.json).

## Actual completion state

| Layer | Observed result |
|---|---|
| contextual export r2 | `WCG1_CONTEXTUAL_EXPORT_PASS`, `WCG1_CONTEXTUAL_OUTER_EXIT=0`, persisted `exit_status=0` |
| generated split reference / candidate | 48 / 49 SV files; 451,321,280 / 453,168,786 bytes |
| guarded pipeline | `KVZAP_RD1_WCG1_PIPELINE_OUTER_EXIT=1`, persisted exit 1 |
| full-run wrapper | `KVZAP_RD1_WCG1_OUTER_EXIT=1`, result-root exit 1 |
| failure | `freeze_rd1_wcg1_input.py:99`, SHA-256 assertion for materialized inline gate |
| final composed input stem | absent; assertion precedes `copytree` |
| result directory | only `exit_status`; no native-binding, Full-KV or Route-A result directory |
| native / side / full PASS | absent; no new DDC, mapped HDL, QoR or tier reports |
| tmux | export, export-r2 and paired-dc panes remain as idle bash |

No process for this failed RD1+WCG1 run remains active. An unrelated EDA
process was observed during inspection; process existence elsewhere does not
mean this run is still running or synthesized. Its details are excluded from
this run's evidence record.

## Source and input identity checked independently

The 19 frozen bundle files, script archive, guard, contextual-source archive,
immutable RD1 archive and target DB match their launch/reference pins. All
121 accepted Chisel project files covered by the existing functional-source
check match; the two declared constructor-forwarding exceptions remain the
already authorized contextual integration scope.

The contextual reference wrapper is **byte-identical**, not merely
whitespace-normalized, to immutable RD1:
`9ea8c57ad4db4170601a20b33bf54b08b2d10457ee55a739f671896010fe8135`.
The candidate wrapper is
`72266ee3e4773e8801d36af6f5574f1004dbbd7ca15748252287ad856a4d2901`.
Its header, field/row shapes, 182,016 member bits, 184,320 suffix bits,
non-table declared state, and 4,608 source gate instances pass the existing
read-only checks. These are source-level checks, not native binding or
post-map retention evidence.

| Pinned input | SHA-256 |
|---|---|
| contextual r2 archive | `fcf677b698d582c47080a865d4a75d690188cb0f6f90a8210e8752f2dfe6ddf1` |
| frozen 19-file script archive | `64bb25f65b38e69042f9e587aa4b6779f0e633d8df6e1c8a3ab7c89cec2d4e3b` |
| guard | `5787e3831aff36654b82d4b2fc179c5517ee41b60358705f00e9f8757e1a1013` |
| immutable RD1 archive | `9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b` |
| target library | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| accepted/current clocking Scala helper | `4bea447a12560a2430b798267447ee3028293f3769b82aedfa191a10985cf394` |

The composed paired archive, five materialized array-proxy checks, final
profile/constraint coverage, native binding and post-map checks were never
reached. They are **not accepted** by these earlier input/source checks.
No DB loading or native library binding is inferred from rehashing the DB.

## Exact failure mechanism

The frozen script performs:

```python
canonical, _ = bind_inline(modules, helper)
gate_text = canonical + '\n'
assert sha256(gate_text.encode()).hexdigest() == 'aeb38a...'
```

The hard-coded hash identifies a different byte representation:

| Representation | Bytes | SHA-256 | Independent authority |
|---|---:|---|---|
| raw emitted inline file, with CIRCT generator comment and trailing blank line | 381 | `aeb38a91977e96c1ea8a7b686d712c39bcd902a4489aedfcb0bb4810b2c1fc28` | current export and accepted wrapper r2 raw file |
| helper module string materialized with one final LF | 342 | `fbc839539af641e061f13ecb9311288b86bae53afa1639093b8e546040aa4556` | current helper extraction and accepted wrapper r2 prepared input |

Both representations are freshly rehashed on the server. Removing only the
raw generated prefix and outer whitespace gives exactly the accepted helper
module body. The helper source matches its accepted pin. SYNTHESIS still
uses `CKLNQD1BWP12T30P140LVT` with unchanged CP/E/Q connections and `TE=0`;
the simulation low-phase latch body is unchanged.

The accepted isolated-wrapper [result JSON](dc_wcg1_wrapper_mapping_retry_result_20261107.json)
already records `fbc839...` at
`input_side_summary/gated/file_sha256/route_a_compact_word_clock_gate.sv`.
Its remote `inputs/gated/` file also rehashes to that value; its `raw/gated/`
file rehashes to `aeb38a...`. The full-freeze script compared canonical bytes
against the raw-file pin. The failure is therefore deterministic with the
unchanged accepted helper, rather than unexplained input drift.

The launch wording that called `aeb38a...` the helper-string SHA was inaccurate;
this inspection corrects the classification without altering that historical
launch or either accepted input. Future pins must name their representation.

## Verification gap and bounded next step

The previous 36 local tests did not execute the freeze-main helper digest
check against the accepted helper, so they missed this integration error.
A repair should explicitly pin helper-source identity, validate any emitted
module body, and pin canonical materialization against the already accepted
prepared-input hash. It must reject native-cell, TE/CP/E/Q, latch or body
changes; it must not delete the hash gate or accept whichever hash appears.

Add direct pure-Python regression coverage for the actual freeze digest path,
permitted missing/exact/empty inline declarations and semantic mutations;
include both raw and canonical pins in diagnostics. The current normalization
routine also has a separate generality limitation for escaped identifiers
and preprocessor newline boundaries. It is not a general semantic-equivalence
proof. The actual reference in this inspection is independently byte-identical,
so that limitation does not explain or weaken this observed comparison.

The completed contextual export can be reused as an immutable input after
all gates pass. A future corrected full attempt must use a new bundle/run ID
and new output stem, retaining this failed run. No additional RTL export is
needed merely to repair the hash-domain mismatch. This inspection applies no
repair, starts no freeze or DC and does not queue an automatic retry.

PM1 remains off, RD2 remains excluded, and the original 2-ns fair-v1 contract
is unchanged. A future full result still requires the original primary tier
and separately paired propagated-clock/hold tiers, with all native gates,
state, drivers, arrays and inputs validated. The current accepted historical
full-top reference remains RD1: 3,388,597.345862 cell-area units / 146.747×
Full-KV control; this failed attempt adds no measurement to it.

## Separate verdicts

| Dimension | Verdict |
|---|---|
| tool/input closure | **FAIL at pre-DC input freeze**; contextual export and listed pre-freeze identities pass |
| mapped-area improvement | **not measured** |
| timing closure: primary/setup/hold/gating | **not measured** |
| structural cleanliness/fanout | **not evaluated for a new map** |
| PPA, zero-cost external services, acceleration, hardware net benefit | **not established** |

The local inspection checks cover JSON consistency, representation hashes,
accepted-pin agreement, source checks, new documentation links and
`git diff --check`. Historical RTL tests and EDA results are not rerun.

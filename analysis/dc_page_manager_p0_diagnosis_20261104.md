# Page Manager control-realization P0 diagnosis — 2026-11-04

## Scope and evidence

This is the next read-only P0 diagnosis after RD1. It changes no production
RTL, generated successor, proxy, constraint, or running DC input, and launches
no compile. It reads the immutable compact-membership saved DDC from
`dc_feasibility_fair_m2p3_compact_20261103_r1` under the unchanged
`dc_feasibility_fair_v1` profile. The separate entry_id repair run is not an
input to this attribution and was not modified.

Saved DDC SHA-256:
`b2908d013cc7182aec8b2c31e8dd77a360a751ac3f12a56f6983df3c03209e69`.
The source hierarchy is stable across the first-refinement and compact runs:
Page Manager area changes only 407,417.9746 -> 407,440.9906. The compact run
has an unrelated mapped entry_id observability defect in M2/P3; it does not
change the Page Manager hierarchy analyzed here.

The accepted read-only query uses `hardware/route_a/dc/probe_page_manager_p0.tcl`.
It performs `read_ddc` and collection/fanin reports only. It
contains no compile, constraint mutation, dont-touch, design write or DDC/HDL
write command. Machine-readable state attribution is in
`dc_page_manager_p0_state_audit_20261104.csv`.

Accepted query identity and closure:

- tmux: `kvzap-control-refine:p13-page-p0-r4`, pane exit 0;
- output: `/home/yaz80/wz_project/dc_project/kvzap_control_projection/read_only/page_manager_p0_20261104_r4/`;
- log: `/home/yaz80/wz_project/chisel_projects/kvpress/logs/page_manager_p0_probe_20261104_r4.log`;
- `KVZAP_PAGE_MANAGER_P0_READ_ONLY_PASS`, `PROBE_READ_ONLY_COMPLETE`, and
  outer `KVZAP_PAGE_MANAGER_P0_OUTER_EXIT=0` are present;
- script SHA-256:
  `f3eaf396b79d01dd099f1949603d8888b98441efb0d7df3caf52da1946568e53`;
- summary/family/cone report SHA-256:
  `75d0f3f583d86305dd2cc53980b75611d1f58ca827cab551bd74407b000469b5`,
  `64f96f5c9c9816d4c8fab9e4cc30e2164d7d6d6f12fd36182f8fda4c7421bf56`,
  `d87afe2f311b095f5cb746098e79babd75fdf6bc09bbc4557c0aad7d75359b8e`,
  `adc6d48f170ee88ee77eeef56c49737b6bae32538cd2f3008bebda2972c84a3b`.

Three earlier diagnostic attempts are preserved rather than overwritten. R1
exposed an incorrect hierarchical cell-pattern query. R2 produced the useful
state/cone data but an invalid cell-as-timing-startpoint command; its subsequent
nonessential timing query was stopped after the native error. R3 corrected the
pin rule but its duplicate 36,720-startpoint timing query was stopped because
the immutable native run already reports that exact path. Only R4 is accepted.

## Mapped concentration

Page Manager is the second-largest mapped Route-A hierarchy after M2/P3:

| metric | Page Manager | fraction |
| --- | ---: | ---: |
| total cell area | 407,440.9906 | 11.242% of Route-A |
| combinational cells / area | 321,955 / 228,323.2560 | 56.038% of Page Manager area |
| sequential cells / area | 62,000 / 179,117.7360 | 43.962% of Page Manager area |
| sequential cells | 62,000 | 10.743% of Route-A sequential cells |

The mapped sequential state has two concentrations:

1. `allocatedLine`: 36,720 cells and 92,555.232 area, 59.226% of Page Manager
   sequential cells and 51.673% of its sequential area. It is one necessary
   parent-control bit per four-page descriptor line; the R5 availability proxy
   does not own or hide it.
2. The 288 stream-slot fields: 24,192 cells and 82,756.464 area, 39.019% of
   Page Manager sequential cells and 46.202% of its sequential area. They hold
   active/fault/durability flags, page identity, tag, valid-record count and
   visible-tail state.

The remaining 1,088 cells cover descriptor-line holds and scalar control.
The source module declares 1,678,810 logical bits, but four large source-only
families are absent from the mapped hierarchy: 1,321,920 release observation
bits and 293,760 verification-shadow bits. The measurement top accepts and
discards the post-durable allocator-release observation, while synthesis
excludes verification layers. These absent bits are not a new optimization
opportunity or mapped-area credit. Removing necessary release semantics is not
selected.

## Combinational and timing roots

The saved-DDC fanin queries expose directed cones. They are useful hotspot
bounds but are not mutually exclusive source attribution and must not be
summed:

| endpoint cone | combinational cells | cell area | fraction of Page Manager combinational area |
| --- | ---: | ---: | ---: |
| `allocatedLine -> reclaimLine` | 135,330 | 85,193.304 | 37.313% |
| payload-durable ready/match | 23,760 | 22,761.480 | 9.969% |
| publication-visibility ready/match | 19,316 | 18,216.240 | 7.978% |
| descriptor-prerequisite valid only | 1,562 | 913.920 | 0.400% |
| append-candidate valid only | 5 | 3.024 | not representative of append data/selection |

The terminal-ready cone is absent in this measurement projection because the
corresponding input is inactive and its ready is unobserved. This is projection
observability, not evidence that a general terminal matcher has zero cost.

`allocatedLine` is both the largest state family and the largest measured
directed combinational cone. The existing native setup report ranks its path
15th among the 20 reported worst paths:

```text
pageManager/allocatedLine_32882_reg
  -> pageManager/reclaimLine_reg[5]
data arrival 2.20 ns; required 1.89 ns; slack -0.31 ns
```

This equals the run's global WNS. The next reported path also ends in Page
Manager (`arbiter/...pending_descriptor_ref -> pageManager/appendState_reg[0]`,
slack -0.31 ns), but crosses the arbiter/delivery composition and cannot be
attributed to Page Manager alone.

## Structural warnings

Page Manager contributes 1,069 LINT-28, 790 LINT-31 and 730 LINT-52 records.
The LINT-28 roots are exact carrier surplus: two 512-bit response-data fields,
two 9-bit fragment indices and smaller delivery/context/status identity fields.
The LINT-31/LINT-52 roots are chiefly zero/aliased upper bits in the 512-bit
reclaim data and wide address/descriptor-line carriers. They reveal typed
interface width mismatch, not missing functional drivers. Adding fake consumers
or deleting required carrier fields to silence them is prohibited. Any future
interface narrowing is a separate contract change and is not an area candidate
in this P0.

## Selected successor candidates

### PM1: exact allocated-line selector realization

This is the first candidate because it targets the dominant 85,193-area
combinational cone and an actual global-WNS path. Retain all 36,720 line bits,
the exact lowest-index selection result, same-cycle reclaim start, reclaim
ordering, drain behavior and the parent-owned R5 control boundary. Compare a
balanced/banked exact-priority implementation against the current lowering in
an isolated 36,720-bit harness before changing Page Manager RTL. No queue,
scan latency, capacity reduction, parent-control black box or relaxed handshake
is authorized by this diagnosis.

### PM2: coordinate-derived stream record and payload lookup

`streamIndexWide(layer, head) = Cat(layer, head)` already determines the
unique accepted slot. Therefore stored `buildLayer` and `buildHead` are exact
functions of the slot and consume 2,592 mapped sequential cells / 8,128.512
area. A bounded candidate may reconstruct them from the selected slot and use
the layer/head carried by `p3_payload_durable_in` for direct slot validation
instead of scanning all 288 records. It must still validate active, fault,
page_ref, generation and tag and preserve ready/fire behavior. The 22,761.480
payload-ready cone is only a pre-change upper bound; not all of it is removable.

Visibility and descriptor-terminal carriers do not contain layer/head, and
append/prerequisite selections can coexist. Their CAM/priority networks are not
silently folded into PM2. Reverse page maps, reduced concurrency and additional
latency are not authorized.

## Disposition and boundaries

P0 finds a concrete Page Manager optimization target rather than a generic
"complex control" explanation. PM1 should proceed first to local equivalence
and isolated small synthesis; PM2 is a lower-risk follow-on candidate with an
exact 2,592-cell state ceiling plus a bounded match-cone opportunity. Neither
candidate is implemented here.

This diagnosis does not establish a new mapped design, whole-Route-A area or
timing improvement, clock-load reduction, PPA, macro implementation, external
descriptor-service cost, system acceleration or hardware net benefit. It does
not reopen pruning, admission, publication, R6 authority, R2 arbitration or
the R5 availability-array proxy boundary.

# Compact wrapper mapped-hotspot attribution — 2026-11-04

## Evidence and method

This read-only audit answers why M2/P3 still occupies 72.8% of Route-A in the
completed diagnostic run `dc_feasibility_fair_m2p3_compact_20261103_r1`.
The entry-id driver repair run is separate and was not altered.  No RTL,
library, synthesis setting or frozen input was changed by this audit.

The analysis streams the mapped wrapper instances, identifies primitive port
directions from the same LVT functional model, and obtains unit area and
sequential classification from the native hierarchical reference report.
Continuation-line attributes are included.  Every parsed reference count
matches the native wrapper reference count (2,179,689 direct instances).

Sequential totals reproduce 400,108 cells and approximately 1,405,170 area;
direct combinational totals reproduce 1,779,320 cells and 1,202,242.944 area.
Unit areas in the native report are rounded to six decimals, so reconstructed
area is approximate.  The native hierarchy reports 2,636,842.5298 including
about 29,429 area in child operators beyond direct local logic.

Remote final report:
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/wrapper_hotspot_audit_20261104_r4.json`.
SHA-256: `604289049ed66899121e9de08f66969ea34ba7b980889add54e2a9ae3f2225e6`.
Diagnostic script SHA-256:
`2338bc8d3a84583a685139e1cb9dd8c01c09243c30f66fcfd56a31a38f3f081b`.
The script is retained as `dc_scripts/kvzap_wrapper_hotspot_20261104.py` on the
same host.  Exploratory parser outputs r1--r3 are not final evidence.

## Exact mapped state concentration

| state family | mapped sequential cells | approximate cell area |
| --- | ---: | ---: |
| compact membership entries | 182,016 | 642,152.448 |
| compact pending-read suffixes | 184,320 | 650,280.960 |
| both tables | 366,336 | 1,292,433.408 |
| persistent reconciliation journal | 17,984 | 63,447.552 |
| remaining wrapper sequential state | 15,788 | about 49,289 |

Both tables are 91.559% of wrapper sequential cells and 49.014% of its entire
hierarchical area.  All 159 compact bits per record remain mapped at 36 x 64
records.  Thus further source-bundle compaction alone is not an established
large saving: most remaining fields are independent information, rather than
the redundant coordinate/header copies removed by P1.

The two 64-bit fields dominate:

| field | cells | approximate area |
| --- | ---: | ---: |
| membership payload_ref | 147,456 | 520,224.768 |
| pending payload_handle_or_address | 147,456 | 520,224.768 |
| logical_position | 34,560 | 121,927.680 |
| source_generation | 18,432 | 65,028.096 |
| transaction identity, combined | 11,520 | 40,642.560 |
| destination endpoint | 6,912 | 24,385.536 |

Payload reference and pending location handle alone account for 39.458% of
wrapper area.  They have different semantic owners and cannot be equated,
truncated or reconstructed from each other without a separate proof.

This is expensive enabled-register storage, not an accidental inclusion of
K/V payload or the already-proxied P3 array interior.  The counts match the
declared metadata capacity and native mapped references.  No synthesis
over-expansion error is demonstrated.

## Combinational paths

Backward cones were traced through direct wrapper primitive gates, stopping
at sequential boundaries.  Unflattened child-operator boundaries stop traversal;
therefore these are incomplete lower bounds, not complete endpoint costs.
In particular, primitive predecessors behind a child comparator may be absent.
Different cones overlap and their areas must not simply be added.

| endpoint group | direct primitive cone area, approximate lower bound |
| --- | ---: |
| materialized work outputs | 310,639.392 |
| checked pack-read issue outputs | 173,207.664 |
| materialized sidecar outputs | 122,734.584 |
| publication member/authority outputs | 122,678.808 |
| sidecar acceptance ready | 25,679.472 |
| reconciliation result register inputs | 17,729.880 |
| fragment acceptance ready | 3,033.408 |

The deduplicated union is 774,658.584, or 64.435% of direct combinational area.
This localizes a large read/selection/association/output-generation surface.
It does not mean that this area is removable: the required functions and
concurrency must still be implemented.  Materialized-work's cone alone is
11.781% of total wrapper area, not the entire 72.8% Route-A share and not a
pure priority-encoder measurement.

The source independently identifies different dynamic reads for materialized
work, checked pack-read, materialized sidecar, fragment payload association,
sidecar association and publication.  These use the same tables with different
indices and stage conditions.  Multiple indexed reads of Reg(Vec(...)) can
produce separate mux/decode networks.  Sharing is a candidate only where
simultaneous-valid and backpressure behavior prove it legal.

## Targeted optimization disposition

1. First target: the membership read/selection implementation.  Compare
   equivalent bank/ordinal decode and mux organizations, identify duplicate
   reads at equal indices, and prove any mutually exclusive read sharing.
   Preserve selection priority, all concurrent legal reads and cycle behavior.
2. Large persistent cost: 366,336 enabled-register bits.  A storage realization
   study may be needed for a larger reduction, preserving 36 x 64 capacity and
   all information/ports.  Any banked-memory or macro alternative must account
   for memory/peripheral cost and latency; it cannot become another free proxy.
3. Materializer mask/selector optimization remains useful, especially for
   timing, but does not remove the record-storage half of wrapper area.
4. Ordinal-indexed reconciliation is a bounded independent candidate.  It does
   not address the two dominant tables and should not be advertised as the
   explanation or solution for the whole 72.8% share.

The next implementation should be justified by a concrete before/after local
structure and equivalent behavior, then screened by focused synthesis before
an expensive complete paired run.  The active driver repair remains the gate
for integration.  No further optimization is implemented by this audit.

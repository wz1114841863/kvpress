# PM1 characterized child-replacement plan — 2026-11-05

## Selected screen

The saved-DDC readiness gate permits a controlled bottom-up screen without
resynthesizing the crashing flat test-only baseline:

1. emit a full-profile `route_a_page_manager_pm1` child with PM1 enabled and
   external descriptor backing retained as the existing typed boundary;
2. require its entire module port header to equal the frozen
   `route_a_page_manager` header except for the module name;
3. read the accepted entry_id-repair mapped top and retain its original Page
   Manager reports as the immutable baseline;
4. analyze/elaborate the new compatible child under a new design name;
5. use DC 2018 `change_link` on the unique `pageManager` instance, then `link`;
6. use `characterize -constraints -connections pageManager` to project the
   real top timing/load/design-rule environment onto the candidate child;
7. map only `route_a_page_manager_pm1`, require the accepted sequential-cell
   count and emit child plus relinked-top diagnostic reports.

The installed DC 2018 command reference was checked directly for
`change_link` compatibility rules and `characterize` environment semantics.
No `-force` or pin map is allowed: any port mismatch must fail.

## Input generation

After the rejected standalone p18 attempt, `EmitPM1PageManagerChirrtl` emits
the complete real-parent control-projection CHIRRTL with only the candidate
Page Manager selector enabled.  The contextually lowered child has exact
144-to-144 port identity with the frozen child.  Its desired child name differs
only to allow both old mapped and new unmapped designs to coexist in one DC
session.  Production/default construction does not select PM1.

`run_pm1_page_manager_successor_generation.sh` performs CHIRRTL emission,
split firtool lowering, exact normalized port-header comparison and immutable
hash capture.  It performs no DC action.

The preparation revision passes Java 21 `Test / compile` and the PM1-enabled
real Page Manager reclaim suite 5/5 after the distinct candidate module name
was introduced.

The executable screen is now implemented and statically checked; see
[`dc_pm1_characterized_replacement_implementation_20261105.md`](dc_pm1_characterized_replacement_implementation_20261105.md).

## Evidence boundary

This bottom-up screen will be more representative than the failed standalone
flat selector because it preserves the real Page Manager and characterized
top boundary.  It is still not identical to the predecessor's original
top-down full compile.  Therefore it may screen a candidate in or out, but a
positive result remains provisional until a complete same-fair-v1 Route-A
successor run.

No state removal, latency change, interface change, clock relaxation, parent
control black-boxing, PPA, external-service cost, acceleration or hardware net
benefit claim is authorized.

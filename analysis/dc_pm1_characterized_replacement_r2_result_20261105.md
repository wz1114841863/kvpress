# PM1 characterized replacement r2 result — 2026-11-05

## Disposition

`pm1_characterized_replacement_20261105_r2` successfully passes the r1 stack
failure but stops at a new fail-closed register-count gate.  It is not a mapped
PM1 result.

Terminal markers are:

- `KVZAP_PM1_CHARACTERIZED_INPUT_PASS`;
- `KVZAP_PM1_CHARACTERIZED_STACK_PASS stack_kb=unlimited`;
- `KVZAP_PM1_CHARACTERIZED_REPLACEMENT_OUTER_EXIT=1`;
- `KVZAP_PM1_CHARACTERIZED_P21_R2_OUTER_EXIT=1`.

There is no native replacement PASS marker and no `summary.tsv`.

## Progress beyond r1

Unlimited stack resolves the prior `VER-30` failure.  DC:

- loads and links the accepted baseline DDC;
- emits the same baseline top/child reports;
- completes both Presto passes for the 322 MB contextual PM1 child;
- elaborates the candidate design;
- selects and links `route_a_page_manager_pm1` successfully.

The candidate analyze/elaborate/link phase uses about 6,448 CPU seconds and
29,544 MB reported session memory.  There is no stack overflow or segmentation
fault.

## New gate failure

The candidate precompile gate reports:

```text
expected 62000 candidate precompile registers, found 62002
```

This occurs before `change_link`, `characterize` or `compile`.  Therefore r2
does not produce candidate mapped HDL/DDC, postcompile reports, mapped area or
timing.

The PM1 selector helper remains purely combinational and contains no `Reg`,
`RegInit`, queue or result register.  The Page Manager construction changes
only the combinational selector expression.  The current 62,000 expectation
comes from the accepted mapped child, while 62,002 is an unmapped elaborated
RTL count.  Thus the observed +2 is not yet evidence of two PM1-added state
bits; it exposes a likely precompile-versus-postcompile counting-layer mismatch.

## Required diagnosis

Do not simply relax the gate.  First establish the legacy contextual child's
precompile count under the same unlimited-stack analyze/elaborate/link path, or
otherwise identify the exact two RTL bits removed by the accepted mapping.
Only if the legacy raw child is also 62,002 may the screen require matched
62,002 precompile state on both sides and retain the accepted 62,000
postcompile candidate gate.

All RTL, frozen inputs, constraints, Page Manager semantics and r1/r2 outputs
must remain unchanged during that bounded diagnosis.  The independent RD1 DC
remained live and untouched at inspection time.

# PM1 characterized replacement r1 result — 2026-11-05

## Disposition

`pm1_characterized_replacement_20261105_r1` did not complete successfully.
Both terminal markers are 139:

- `KVZAP_PM1_CHARACTERIZED_REPLACEMENT_OUTER_EXIT=139`;
- `KVZAP_PM1_CHARACTERIZED_P20_OUTER_EXIT=139`.

There is no native replacement PASS marker and no `summary.tsv`.

## Completed stages

The immutable input gate passed, including the accepted DDC, p19 candidate,
p19 manifest and target-library checks.  DC then:

- loaded the target library;
- read all 405 designs from the accepted entry-id-repair DDC;
- linked the accepted Route-A top;
- resolved the existing Page Manager child;
- emitted the baseline top and child QoR, area and setup reports.

The recovered baseline child remains consistent with the accepted result:

- sequential cells: 62,000 in QoR;
- combinational area: 228,322.580768;
- noncombinational area: 179,128.657829;
- total cell area: 407,451.238597.

## Failure

The failure occurred while DC analyzed the 322 MB contextual PM1 child, before
candidate elaboration completed:

```text
route_a_page_manager_pm1.sv:779912: Stack overflow. Cannot continue. (VER-30)
```

DC then terminated with segmentation-fault exit 139.  The source location is
the start of the 146,880-bit `releasePending` reduction concatenation, so it is
a high-stack Presto elaboration contour rather than a port mismatch.

The p20 shell inherited an 8,192 KiB stack.  The accepted full DC runner
explicitly raises this to unlimited before invoking `dc_shell`; the new
replacement runner omitted that established protection.  This is the first
bounded correction to test.  It is not yet proof that unlimited stack alone
will complete the candidate.

## Evidence boundary and recovery

The run never reached `change_link`, `characterize`, candidate compile,
postcompile register/proxy checks, candidate DDC/mapped HDL or relinked-top
reports.  Therefore r1 provides no PM1 mapped-area or timing comparison.

Preserve r1 as the failed diagnostic.  A successor must use a new result root,
add the same `ulimit -s unlimited` protection as the accepted full DC runner,
retain all existing fail-closed gates, and rerun without changing RTL,
constraints, state, parent control or candidate input.

The independent RD1 paired DC remained live and untouched at inspection time.

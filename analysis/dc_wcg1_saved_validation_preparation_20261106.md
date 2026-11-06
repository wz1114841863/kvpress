# WCG1 saved-artifact summary repair preparation

Authorization: repair the summary and accept existing mapped artifacts using
a short validation; **no DC restart and no RD2 access**.
Source failure: `dc_wcg1_bank_mapping_error_diagnosis_20261106.md`.

`tools/check_wcg1_bank_mapping.py` now takes native **Total cell area** as
authority, cross-checks its sequential/combinational components and QoR, and
rejects missing, duplicate, nonfinite, zero or inconsistent values. A finite
scalar must agree with the report. Recovery of r1's empty scalar requires an
explicit mode, matching UID-101 signature and pinned original inputs/artifacts;
it never edits the source metrics. Precision timing reports, rather than
rounded QoR WNS or scalar rounding, supply accepted slack values.

The future Tcl collector reads the same native report instead of requesting
the unsupported design attribute, and fails before side PASS if area fields
are invalid. Its reader is tested using ordinary Tcl. The updated DC script
is not executed in this batch; no design source or constraint is changed.

The short runner `run_wcg1_saved_artifact_validation.sh` invokes only Python
and checksum utilities. It does not source the EDA environment or load a DDC.
Its new output and sibling receipt directories are separate from original r1.
Before and after the check it verifies archive, all frozen inputs, actual DB,
launch and diagnosis provenance, and the existing report/HDL/DDC inventory.
The original complete source tree is hashed before/after to prove it was not
modified. The original outer exit remains 1; successful sidecar validation
will have its own PASS and outer exit 0.

Additional acceptance checks retain all 10,176 bits/128 gates, inspect the
actual clock-gate **increment** column (not its transition), validate all
four saved SDCs against the 2-ns numerical profile with reset timed and no
false/multicycle exception, inspect native precision setup/hold/gating checks,
and retain residual lint counts. Raw gated hold failure remains recorded;
acceptance requires positive repaired area savings, repaired setup/hold and
gate-check closure, and no violated repaired constraints on both sides.

Focused regression count is 26, including recovery opt-in, preserved metrics,
missing/duplicate/nonfinite/inconsistent area, stale scalar rejection,
redirected native errors, clock capture increment, Tcl producer behavior,
and constraint drift. The revised checker also passes locally on the actual
copied artifacts, including raw hold failure and repaired timing closure.
That local check is preparation, not remote input/library acceptance.

Next: freeze this repaired validator in a new independent bundle and run the
short remote validation against untouched r1. Only its separate completed
receipt and result can supersede the failed summary disposition. This screen
remains one bank at one library corner, not full Route-A, PPA or physical
signoff; no full-wrapper equivalence or system/hardware benefit is claimed.

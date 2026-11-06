# WCG1 r1 postcheck failure diagnosis

Run: `wcg1_bank_mapping_sta_20261106_r1`.
Disposition: **both native mapping sides completed; summary failed; not accepted**.
This is a read-only diagnosis of the remote run and local copies of its
existing artifacts. No RTL/tooling was modified, no tool was restarted, and
RD2 was neither queried nor changed.

Evidence: [`dc_wcg1_bank_mapping_error_diagnosis_20261106.json`](dc_wcg1_bank_mapping_error_diagnosis_20261106.json).
Original inputs/launch remain frozen in
`dc_wcg1_bank_mapping_launch_20261106.md` and its JSON.

## Located failure

Reference and gated each have native `exit_status=0`, both stage-reported
markers and their executed `KVZAP_WCG1_SIDE_RUN_PASS` marker. Both sides
wrote raw and hold-repaired DDC, mapped HDL/SDC and native reports.
The launcher subsequently failed in `check_wcg1_bank_mapping.py`, at
`m[key] = float(m[key])`, with:

```text
ValueError: could not convert string to float: ''
KVZAP_WCG1_MAPPING_OUTER_EXIT=1
```

All four `metrics.tsv` files have an empty `total_area` value. Their producer
in `screen_wcg1_bank_sta.tcl` requests:

```tcl
get_attribute [current_design] area
```

The installed DC O-2018.06-SP1 does not provide this design attribute. Each
native log contains the actual warning twice, once per saved stage:

```text
Warning: Attribute 'area' does not exist on design 'wcg1_reference'. (UID-101)
```

The gated log names `wcg1_gated` instead. DC returns an empty value without
aborting the Tcl, allowing native side PASS; Python then correctly refuses
to turn the empty field into a numeric area. The unsupported lookup was
introduced by the WCG1 screen tooling. Preparation tested linked cells,
gating checks and synthetic postcheck fixtures, but did not exercise this
mapped-design attribute lookup. Fixtures supplied finite areas and missed
this native warning/empty-field case.

This does not mean that area was lost or zero. Each native `area.rpt` has a
defined **Total cell area**, checked against its combinational plus
noncombinational area. Its separate **Total area** is undefined because
ZeroWireload supplies no interconnect area; that field must not be used as
a substitute. Do not convert missing metrics to zero or bypass this gate.

## Existing native observations, pending short acceptance repair

| Saved stage | Reference cell area | Gated cell area | Reduction | Gated worst hold slack |
| --- | ---: | ---: | ---: | ---: |
| raw | 56,919.576720 | 47,433.287347 | 16.6661% | -0.0179208 ns |
| hold repaired | 56,919.576720 | 47,512.919348 | 16.5262% | +0.00352895 ns |

The planned hold phase addressed a real issue: raw gated QoR reports 9,992
hold violations and rounded hold TNS -68.32 ns. Repaired gated QoR reports
zero hold violations and zero hold TNS. The additional repair costs 79.632001
cell area; do not quote raw area alone as an accepted implementation cost.

Worst setup slack is +1.06405 ns in all four scalar snapshots and precision
reports; setup TNS and violating-path counts are zero. Gated enable checks
have worst setup +1.64934 ns and hold +0.0661304 ns before and after repair.
Both repaired `report_constraint -all_violators` reports say there are no
violated constraints. The positive 3.53-ps gated hold margin is small and
belongs only to this 2-ns, single slow-corner, cell-delay/wire-load screen;
it does not establish physical/multicorner hold signoff.

Repaired reference sequential/combinational areas are
36,662.137178 / 20,257.439542. Repaired gated areas are
26,727.287798 / 20,785.631550. Thus smaller sequential cells retain a net
area reduction after the increased combinational/buffer cost in this bank.
The critical setup slack does not improve in this screen.

## Independent artifact and structural audit

- Remote archive, all eleven input files, DB and SHA256SUMS rechecked against
  launch pins. The copied input manifest matches the frozen SHA-256
  `5f03ffd7ba5897699cc53f9928391137e9ad21a1b1297bd564480071999fde4e`.
- All four DDC hashes match remote checksums. JSON records hashes for native
  reports, metrics, mapped Verilog/SDC and DDC; original files are preserved.
- Both raw/repaired mapped HDLs independently contain every one of the
  64 x (79+80) named data cells. Reference retains enabled EDFQD cells;
  gated retains ordinary DFQD cells and 128 native CKLNQ gates. No data bit
  was removed. No GTECH/SEQGEN instances remain in mapped HDL.
- All snapshots retain 2-ns clocks and propagated-clock state. Gated min
  capture paths actually traverse positive-delay CKLNQ Q arcs and downstream
  clock buffers; the audit extracts the increment column, not merely the
  transition column. Native gate setup/hold checks are present.
- No native Error/Fatal occurs in either native log or any redirected report.
  Each check-design report has the same 12 LINT-28 warnings, unused ports
  of two DesignWare equality comparators. These are retained warnings,
  not a zero-lint claim. Timing checks show no unconstrained-endpoint warning.
- The Python exception remains in launcher.log. Postcheck PASS, final run
  PASS and outer exit 0 are absent. Native success must not erase that fact.

## Minimal repair path

Use the exact native **Total cell area**, validate that it is unique, finite
and positive, and cross-check it against combinational plus sequential area.
Future collection should fail at the producer if required scalars are
missing. Add a regression reproducing UID-101 plus an empty area scalar;
also cover a missing report area, inconsistent totals and nonfinite values.

Then perform a separately versioned, provenance-recorded postcheck of the
already mapped artifacts. There is no need to analyze, compile or remap.
Keep the original r1 metrics, hashes, logs and failed outer marker unchanged;
record any derived scalar in the new validation record, not by silently
editing the frozen run. This diagnosis itself performs neither that repair
nor the new validation run.

No whole-wrapper/Route-A area ratio is updated. These observations do not
establish PPA, external-service cost, system speedup or hardware net benefit.

# PM1 saved-DDC short-validation result — 2026-11-06

## Disposition

Run `pm1_saved_ddc_validation_20261106_r1` completed successfully.  It closes
the r3 stale-collection summary defect without repeating analyze,
characterization or compile.  The existing mapped PM1 diagnostic is now
accepted at the bounded saved-DDC replacement-screen tier.

All terminal gates pass:

- `KVZAP_PM1_SAVED_DDC_NATIVE_PASS`;
- `KVZAP_PM1_SAVED_DDC_POSTCHECK_PASS`;
- `KVZAP_PM1_SAVED_DDC_OUTER_EXIT=0`;
- `KVZAP_PM1_SAVED_DDC_P24_OUTER_EXIT=0`;
- zero native `Error:` or `Fatal:` lines and no residual validation process.

DC reports 584 CPU seconds, about 9.7 minutes, and 7,455 MiB session memory.
This is materially shorter than the r3 3.3-hour child mapping because it only
reads saved DDCs, links and reports.

## Input and structural closure

The runner verifies the accepted top DDC, r3 candidate DDC, paired mapped HDL,
r3 provenance manifest, fair-v1 profile, target library and validation scripts.
The complete non-empty summary is:

- validation kind: `saved_ddc_only`;
- Page Manager boundary pins: 4,289;
- baseline registers: 62,000;
- candidate registers: 62,000;
- candidate clocks: one;
- candidate R5 proxy instances: one;
- relinked-top registers: 577,106.

The expected `UIO-92` warnings report the same named R5 proxy design in both
saved DDC libraries.  Link priority selects the context-appropriate copy; the
exact one-proxy gate passes and no native error is emitted.

## Reproduced mapped evidence

The structured `evidence.json` exactly reproduces r3:

| metric | accepted baseline | PM1/relinked | change |
|---|---:|---:|---:|
| Page Manager cell area | 407,451.238597 | 390,334.056566 | -17,117.182031 (-4.201%) |
| top cell area | 3,622,375.558791 | 3,605,258.376760 | -17,117.182031 (-0.473%) |
| setup WNS | -0.31 ns | -0.31 ns | unchanged |
| setup TNS | -8,577.41 ns | -8,441.79 ns | +135.62 ns |
| setup violating paths | 35,897 | 35,293 | -604 |
| hold WNS | 0.00 ns | -0.01 ns | one new violating path |
| lint warning lines | 44,533 | 44,537 | +4 |

The candidate child independently reports setup WNS -0.28 ns, TNS -1.74 ns,
seven setup-violating paths and one rounded -0.01-ns hold violation.  All lint
category counts match the r3 native reports and contain zero error lines.

## Conclusion and boundary

PM1 is now completely validated for its intended bottom-up screening role:
it preserves registers, ports, clock and proxy closure and yields a real 4.201%
Page Manager area reduction.  Its whole-Route-A area effect is only 0.473%,
setup WNS does not improve, and hold/high-fanout/lint cleanliness regress
slightly.  It is therefore a valid small cumulative area optimization, not a
major Route-A reduction or timing-closure solution.

No clean 3.3-hour replay is required solely to repair the stale summary.  A
future production acceptance still requires PM1 in a complete integrated
same-fair-v1 successor compile.  This result is not PPA, physical timing,
external-service zero cost, acceleration or hardware net benefit.

The independent RD1 paired DC remained live and untouched throughout this
short validation.

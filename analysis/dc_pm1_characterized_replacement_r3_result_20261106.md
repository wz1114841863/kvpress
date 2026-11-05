# PM1 characterized replacement r3 result — 2026-11-06

## Disposition

Run `pm1_characterized_replacement_20261105_r3` completed child mapping and
emitted the expected DDC, mapped Verilog and baseline/candidate/relinked-top
native reports.  The native replacement PASS and both outer exit-zero markers
are present.  However, two terminal `SEL-001` errors leave the run formally
unclean and two summary fields empty.  This run is accepted as a useful
bottom-up mapped diagnostic, not as a clean replacement-screen closure.

The independent RD1 paired DC was still live and advancing at the inspection
snapshot on 2026-11-06; no RD1 completion conclusion follows here.

## Tool and input closure

The remotely recomputed hashes match the r3 input manifest:

- accepted entry-id DDC:
  `29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`;
- contextual PM1 child:
  `dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671`;
- candidate-input manifest:
  `36ce5058294a74d8f7852e65ce765b1138323978f28d17a0e7f4a899784617fa`;
- replacement Tcl:
  `7c1e3c70b128925afcd9bd51a38768de7466420757b4a10df68360a2709250ce`;
- runner:
  `9b4e9601e0ad0abdd5871ff20dde1bd7b9d11a8068caefeaab7475feb902379b`;
- target library:
  `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.

The stack guard passes.  Candidate precompile registers are 62,002;
postcompile sequential cells are 62,000; one characterized clock is present.
The mapped candidate artifacts are non-empty:

- DDC: 13,433,344 bytes, SHA-256
  `38038fb2c9edc434d6bc3059e9166c57c63cfed78269e2765a2f758e21fddb0e`;
- mapped Verilog: 42,063,760 bytes, SHA-256
  `e98ef9cac40e87d40f5ed8426bc0f2dd09ac8b5eb2e51d508a31fe3179eb9aa2`.

## Area direction

Against the accepted mapped Page Manager in the saved entry-id top:

| metric | accepted child | PM1 child | delta |
|---|---:|---:|---:|
| total cell area | 407,451.238597 | 390,334.056566 | -17,117.182031 (-4.201%) |
| combinational area | 228,322.580768 | 210,697.702823 | -17,624.877945 (-7.719%) |
| noncombinational area | 179,128.657829 | 179,636.353743 | +507.695914 (+0.283%) |
| leaf cells | 383,954 | 349,698 | -34,256 (-8.922%) |
| combinational cells | 321,954 | 287,698 | -34,256 (-10.640%) |
| sequential cells | 62,000 | 62,000 | 0 |

The relinked-top cell area changes from 3,622,375.558791 to
3,605,258.376760, the same absolute -17,117.182031 reduction and a -0.473%
top-level change.  This is a characterized bottom-up replacement observation;
it is not a complete integrated same-fair-v1 successor compile.

## Timing direction

The relinked top retains setup WNS at -0.31 ns.  Absolute TNS improves from
8,577.41 ns to 8,441.79 ns (-135.62 ns, -1.581%), and violating setup paths
fall from 35,897 to 35,293 (-604, -1.683%).  PM1 itself reports WNS -0.28 ns,
TNS -1.74 ns and seven setup-violating paths after characterization.

Timing is not closed.  A new candidate/relinked-top hold violation appears at
`appendKind_reg[0]`, with reported slack -0.005321 ns (rounded QoR WNS
-0.01 ns), one hold-violating path.  The candidate child also reports one
unconstrained maximum-delay endpoint before reintegration;
`relinked_top/check_timing.rpt` does not retain an unconstrained endpoint.

## Structural cleanliness

The relinked top has 44,537 `check_design` warning lines versus 44,533 in the
accepted top, a net increase of four.  The category deltas are LINT-28 +6,
LINT-31 -1 and LINT-52 -1; LINT-29, LINT-33 and LINT-55 are unchanged.  The
entry-id warning population remains unchanged, so the previous entry-id repair
does not regress.  Top `check_timing` reports three high-fanout nets versus
two in the accepted top; the candidate child identifies clock with 62,001
loads and reset with 30,085 loads.  Structural cleanliness therefore does not
pass.

## Terminal error diagnosis

All mapped artifacts and reports were written before the two errors:

```text
Error: No such collection '_sel11' (SEL-001)
Error: No such collection '_sel19' (SEL-001)
```

The screen saves `baseline_registers` and the final candidate `proxy_cells` as
DC collection handles.  The final top relink invalidates those handles.  The
summary then calls `sizeof_collection` on both stale collections, producing
the two errors and leaving these fields blank:

- `baseline_registers`;
- `candidate_proxy_instances`.

The earlier fail-closed gates already observed 62,000 baseline registers and
one retained candidate proxy, otherwise execution would have stopped before
mapping.  Nevertheless, DC command errors did not raise the surrounding Tcl
`catch`, so the script incorrectly printed PASS and exited zero.  Exit zero is
therefore insufficient for clean acceptance.

The bounded correction is to snapshot integer counts immediately when the
collections are valid, use only those scalars after relink, and add an explicit
error/summary completeness gate.  Do not automatically repeat the 3.3-hour
mapping run solely from the terminal markers; first decide whether a short
saved-DDC closure can validate the existing mapped artifacts or whether a
clean r4 replay is required.

This result does not establish PPA, physical timing, external-service zero
cost, system acceleration or hardware net benefit.

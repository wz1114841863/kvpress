# PM1 exact allocated-line selector implementation — 2026-11-04

## Scope

This is the user-authorized isolated implementation and small-synthesis
preparation for PM1 from `dc_page_manager_p0_diagnosis_20261104.md`. It does
not modify or instantiate logic in production `RouteAPageManager`.

The candidate retains all 36,720 `allocatedLine` bits and implements an exact
lowest-set-bit selector as 574 fixed 64-entry banks. It selects the lowest set
bit inside every bank, selects the lowest non-empty bank, and concatenates the
two indices. The final 48-entry bank is zero-padded. The result is purely
combinational: there is no queue, state reduction, extra cycle, changed
reclaim order, changed handshake or changed R5 authority boundary.

`RouteAExactLowestPrioritySelector.banked` also preserves the raw empty-input
result of the current Chisel `PriorityEncoder`: `selected_valid` is false and
the index is the terminal entry. Page Manager guards the index with the
valid/OR result, but preserving this convention makes the isolated comparison
bit-exact for every input vector.

## Local equivalence evidence

- Java 21 `Test / compile`: PASS.
- Bounded miter: 13 input bits, 8-entry banks and a five-entry partial final
  bank; all 8,192 vectors compare the candidate directly with Chisel
  `PriorityEncoder`. PASS, outer `KVZAP_PM1_BOUNDED_MITER_EXIT=0`, log
  `/tmp/kvzap_pm1_selector_bounded_20261104_r3.log`, SHA-256
  `dcb42eeb08c32c5f849389e61ea63a8c2b95708bd0d3a22cd9ca79e36247812c`.
- Exact 36,720-entry geometry: zero, all-one, every 36,720 one-hot index,
  66 selected two-hot bank/tail-boundary cases, 512 random dense vectors and
  512 random eight-hot vectors compare candidate outputs against their exact
  software expectation. PASS, outer `KVZAP_PM1_FULLSCALE_CHECK_EXIT=0`, log
  `/tmp/kvzap_pm1_selector_fullscale_20261104_r3.log`, SHA-256
  `d4e0405b810ba69c239ae74d09e2e404450f10cca671fc3a9b1611b0b776b691`.

The failed diagnostics are preserved rather than relabelled as validation.
The first run exposed the different `PriorityEncoder(Vec)`/UInt ordering plus
a simulator-only wide-port initialization warning. The second run fixed bank
ordering and then exposed that Chisel's empty-input result is the terminal
index rather than zero. Their logs are
`/tmp/kvzap_pm1_selector_miter_20261104_r1.log` (SHA-256
`775ba0eb40a63a87e8c4a82a6ba60748455e7fed79713700571fe7cd557453cb`)
and `/tmp/kvzap_pm1_selector_miter_20261104_r2.log` (SHA-256
`8129713c69100ff89fa56f68fc27b72a45ce8835b64c81fbbe31ed17056544ca`).

## Isolated synthesis inputs

`RouteAPM1SelectorEmitter` emits two test-only combinational tops with the
same 36,720-bit input and 16-bit selected index:

- original Chisel `PriorityEncoder`:
  `/tmp/kvzap_pm1_screen_inputs_20261104_r1/pm1_original_selector.sv`,
  SHA-256 `8019d8c27b3920ec97448fcdf381b12a4e2655522a9f81d46fd194208ab023db`;
- PM1 banked selector:
  `/tmp/kvzap_pm1_screen_inputs_20261104_r1/pm1_banked_selector.sv`,
  SHA-256 `1603cdecda927ba02bead96ced5939eb2b356f4ea4acccabd6f5b794ffda7fac`.

The screen launcher verifies the immutable fair-v1 profile, all seven
constraint numbers, target-library hash and constraint-Tcl hash. DC maps each
side independently with the same command and writes native DDC, mapped HDL,
QoR, area, timing, constraint and design-check reports. The screen
contains no registers, Page Manager state machine, descriptor service or
other Route-A logic.

At this implementation checkpoint, no remote DC result exists. Generated SV
size is not area evidence. Acceptance requires both side PASS markers, the
overall PASS, `KVZAP_PM1_SELECTOR_SCREEN_OUTER_EXIT=0`, immutable
manifest/hashes and the native reports.

## Boundaries

This batch establishes a locally equivalent PM1 candidate and a reproducible
isolated-screen package only. It does not establish mapped-area or timing
improvement, Page Manager integration correctness, complete Route-A timing,
clock-load change, lint improvement, PPA, external-service cost, acceleration
or hardware net benefit. It does not reopen pruning, admission, R3
publication, R6 authority, R2 arbitration or the R5 availability-array proxy.

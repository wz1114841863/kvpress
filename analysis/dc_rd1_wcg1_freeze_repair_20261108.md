# RD1+WCG1 input-freeze repair and direct regression — 2026-11-08

The user authorizes repairing the hash gate, adding regression coverage,
reusing the completed contextual export, and starting a new immutable full
paired DC in independent tmux. This batch repairs preparation only; native
mapping/STA and launch evidence belong to the subsequent run record.

## Change

`tools/freeze_rd1_wcg1_input.py` now independently pins the accepted helper
source and its canonical module-plus-LF representation. The raw firtool-file
hash is recorded separately, rather than used to validate canonical bytes:

| Representation | SHA-256 |
|---|---|
| helper Scala source | `4bea447a12560a2430b798267447ee3028293f3769b82aedfa191a10985cf394` |
| canonical 342-byte prepared inline | `fbc839539af641e061f13ecb9311288b86bae53afa1639093b8e546040aa4556` |
| raw 381-byte emitted file | `aeb38a91977e96c1ea8a7b686d712c39bcd902a4489aedfcb0bb4810b2c1fc28` |

The canonical pin comes from the already accepted isolated-wrapper r2
prepared-input record, not a newly accepted arbitrary hash. Missing or empty
matching inline declarations can still be completed from the pinned helper;
a nonempty emitted body must match that helper. Unexpected prefix logic,
preprocessor directives, multiple modules, or semantic mutations are rejected.
Failure messages identify source/raw/canonical representations and identities.
Composition records now include the inline provenance details.

The reference wrapper must be byte-identical to immutable RD1; candidate
headers are compared without whitespace deletion. This avoids relying on the
older normalization routine as a general semantic proof. No RTL, interface,
capacity, state, clock/reset, concurrency, handshake or source-owner contract
changes. The baseline archive/Page Manager pins remain fixed production
constants; only tests substitute them for synthetic fixtures.

## Validation

Command:

```bash
.venv/bin/pytest -q tests/test_rd1_wcg1_freeze.py tests/test_rd1_wcg1_full_paired.py tests/test_wcg1_wrapper_mapping.py
```

**48 tests pass.** The new file has 20 cases, including real `freeze.main`
composition with synthetic 48-unit baseline provenance and the actual pinned
helper. These are Python preparation checks, not new RTL functional tests.
They verify accepted raw/canonical/absent/empty representations, unchanged
47 units plus one replaced and one added unit, 49 entries, unchanged Full-KV,
PM1 off/RD2 excluded, no overwrite, and rejection before output creation.
Negative controls cover the original wrong hash domain, helper/reference
drift, native cell/CP/E/TE/Q changes, latch/body changes and unexpected prefix
logic/directives. Thus the previously unexecuted digest path is exercised.
Shell syntax, CLI help, Tcl completeness and `git diff --check` also pass.
No model, HDL simulation or EDA is run by this repair batch.

## Retry boundary

Reuse only the successful immutable
`rd1_wcg1_contextual_20261107_r2` export. Preserve the failed
`dc_feasibility_fair_rd1_wcg1_20261107_r1` and its original script bundle.
The new run is `dc_feasibility_fair_rd1_wcg1_20261108_r2`, with a new bundle,
input stem, result directory, log and independent tmux window. All other
bundle files, original compile policy and 2-ns constraints stay unchanged.
Keep PM1 disabled and RD2 excluded.

Input composition, 16 typed port families, 12 real owners, R5 checks, five
array proxies, fair profile/coverage and full native gate binding must pass
before formal compilation. Preserve `primary_raw`, `propagated_raw` and
`propagated_hold_repaired` separately for both complete tops, including all
repair costs. No area/timing conclusion follows from this repair or launch.

# Migration record: `tmp/mem` to Route-A hardware workspace

The former `tmp/mem` was ignored by Git.  Its useful generic behavior has been
reimplemented under this version-controlled directory before removal:

- single physical macro per invocation;
- explicit capacity, width, and port validation;
- generated CACTI input plus raw stdout/stderr retention;
- execution from the CACTI source checkout, which is required for technology
  table lookup; and
- separated requested capacity from CACTI line/minimum-array padding.

The original BRISK-KV inventory evaluator is intentionally not carried forward
as executable Route-A tooling.  It assumes a distinct Chisel/RTL memory CSV,
28-nm interpolation, fixed exclusive 1R+1W ports, and a different hardware
scope.  Reusing those defaults would silently violate the A4.12 frozen
interface boundary.

The prior bundled executable is not retained: its upstream URL, commit, build
recipe, and license provenance could not be established.  Route-A uses the
tracked public source lock and locally rebuilt executable instead.  The former
ignored directory may be deleted only after the tracked workspace builds and
the compatible smoke record has been retained under `analysis/experiments/`.

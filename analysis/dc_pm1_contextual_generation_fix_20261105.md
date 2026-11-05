# PM1 contextual generation fix — 2026-11-05

## Problem

The rejected p18 input emitted `RouteAPageManager` as a standalone top.  That
changed firtool lowering context and retained 74 typed bundle fields that the
real measurement parent does not consume.  The exact replacement port gate
correctly rejected the resulting 218-port module against the frozen 144-port
child.

## Fix

`RouteAMeasurementDut` now accepts one optional
`bankPageManagerAllocatedLineSelector` construction parameter.  It defaults to
false and is forwarded only to the existing Page Manager realization flag.
Therefore all production and accepted control-projection construction points
remain on the legacy selector unless a caller explicitly selects PM1.

The PM1 emitter now elaborates the complete full-profile
`RouteAControlProjection` with that flag enabled.  Its top remains
`route_a_control_projection`, while only its Page Manager child is named
`route_a_page_manager_pm1`.  Firtool will consequently see the same real
parent connections and contextual dead-port pruning as the frozen successor.

The successor-generation script consumes the resulting
`route_a_control_projection_pm1.fir`, then retains the same strict child port
identity gate.  No force relink, pin mapping, interface waiver or DC invocation
was added.

## Local verification

- Java 21 `Test / compile`: pass;
- `ControlProjectionElaborationSpec`: 1/1 pass, including default legacy-child
  and explicit contextual PM1-child checks;
- PM1-enabled `RouteAReclaimSpec`: 5/5 pass;
- generation script `bash -n`: pass;
- `git diff --check`: pass.

This establishes only corrected generation context plus the existing
functional coverage.  Exact full-profile post-firtool port identity still must
pass remotely before any saved-DDC replacement screen is allowed.

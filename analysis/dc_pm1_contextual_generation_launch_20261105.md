# PM1 contextual successor generation launch — 2026-11-05

## Scope

This run regenerates the PM1 Page Manager under the real full-profile
`RouteAMeasurementDut` parent so firtool sees the same contextual port-pruning
environment as the frozen paired successor.  It performs no DC invocation.

The default production/control-projection construction remains on the legacy
selector.  Only this PM1-specific emitter explicitly selects the banked exact
lowest-index realization.

## Frozen inputs and launch

- source revision: `6dc1671`;
- baseline successor root:
  `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/rd1_shared_e5d3107_p15`;
- output root:
  `/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/pm1_contextual_6dc1671_p19`;
- tmux window: `kvzap-control-refine:p19-pm1-context-freeze`;
- log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_contextual_p19_generation_20261105.log`;
- terminal outer marker:
  `KVZAP_PM1_CONTEXTUAL_P19_GENERATION_EXIT=<code>`.

Before launch, the three contextual Scala inputs and generation script were
verified byte-identical between the local checkout and remote workspace.  The
respective SHA-256 values are:

- `d48acae09041a6a9643d8309920b33c85ac24c11802c3ce1d162ad8e2682b8d8`;
- `8d1a29429d372df23a1e402c97a839ddea9f444d844139b69b4cdfb107ccb81f`;
- `7a9fc95edb17ddbbc6c7422322d4cd948ad96d52936e0ee4f9f36f03978f0ffe`;
- `2b431e05213856eb0d994c0338c180f18adae8b241dfc89c27e1e4ba95f51dcd`.

The output root was absent, the remote filesystem had about 586 GiB free, and
the separate RD1 DC remained live before launch.

## Launch state and completion gate

The p19 shell, sbt/Java process and log were live in full-parent CHIRRTL
elaboration.  The independent `kvzap-control-refine:p16-rd1-dc` window remained
live and untouched.

Acceptance requires all of the following after completion:

- outer exit zero;
- `KVZAP_PM1_PAGE_MANAGER_PORT_IDENTITY_PASS`;
- `KVZAP_PM1_PAGE_MANAGER_SUCCESSOR_PASS`;
- non-empty contextual CHIRRTL and split candidate child;
- recorded hashes that recheck exactly;
- 144 candidate child ports matching the frozen contextual child.

This launch is not mapped-area, timing, PPA or hardware-benefit evidence.  A
passing freeze would only authorize the separately controlled characterized
saved-DDC replacement screen.

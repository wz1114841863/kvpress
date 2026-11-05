# PM1 characterized replacement r2 launch — 2026-11-05

## Single controlled delta

This successor preserves r1's accepted DDC, contextual PM1 child, target
library, Tcl, constraints, relink/characterize flow and all register/proxy
gates.  Its only execution delta is a fail-closed unlimited-stack guard before
`dc_shell`.

The failed r1 result remains preserved and is not reused or overwritten.

## Run identity

- run ID: `pm1_characterized_replacement_20261105_r2`;
- tmux: `kvzap-control-refine:p21-pm1-characterized-r2`;
- result root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/pm1_characterized_replacement_20261105_r2`;
- outer log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_characterized_p21_r2_dc_20261105.log`;
- runner-native terminal marker:
  `KVZAP_PM1_CHARACTERIZED_REPLACEMENT_OUTER_EXIT=<code>`;
- tmux-wrapper terminal marker:
  `KVZAP_PM1_CHARACTERIZED_P21_R2_OUTER_EXIT=<code>`.

The runner is frozen at source revision `5157dfd` with SHA-256
`adb68b432b465019018ac00809f2ece6503a2cdffa30616064e7105bd2c66b5e`.
The replacement Tcl remains
`9d210958e95d618c8cfe8c232e90204615b54167c43c7b39d19d5cebc18f35a3`.

## Launch closure

Before launch, the remote runner hash matched, the remote shell demonstrated
that it can establish unlimited stack, the new result root was absent, the
accepted input hashes remained closed and about 584 GiB was free.

After launch:

- `KVZAP_PM1_CHARACTERIZED_INPUT_PASS` is present;
- `KVZAP_PM1_CHARACTERIZED_STACK_PASS stack_kb=unlimited` is present;
- the runner, DC process and p21 window are live;
- the independent RD1 DC remains live in `p16-rd1-dc` and is untouched.

This is a launch record, not a mapped result.  Completion still requires the
native replacement PASS, both outer exits zero, 62,000-register and R5-proxy
closure, candidate DDC/mapped HDL and all baseline/candidate/relinked-top
reports.

## Completion update

The unlimited-stack correction succeeds: candidate Presto analysis,
elaboration and link complete without a tool crash.  The run then stops at the
precompile state gate because the unmapped candidate has 62,002 registers
against the 62,000 mapped-baseline expectation.  Both outer exits are 1.  See
[`dc_pm1_characterized_replacement_r2_result_20261105.md`](dc_pm1_characterized_replacement_r2_result_20261105.md).
No relink, characterization, compile or mapped comparison occurred.

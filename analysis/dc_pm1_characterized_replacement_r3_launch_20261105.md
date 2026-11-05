# PM1 characterized replacement r3 launch — 2026-11-05

## Authorized delta

R3 changes only the replacement screen's stage-count expectations after the
accepted same-layer legacy probe:

- candidate precompile registers: 62,002;
- accepted and candidate postcompile registers: 62,000.

The accepted DDC, contextual PM1 child, input manifest, target library,
unlimited-stack guard, fail-closed relink, characterization method, proxy
retention and medium-effort child-only compile are otherwise unchanged.

## Run identity

- run ID: `pm1_characterized_replacement_20261105_r3`;
- tmux: `kvzap-control-refine:p23-pm1-characterized-r3`;
- result root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/pm1_characterized_replacement_20261105_r3`;
- outer log:
  `/home/yaz80/wz_project/chisel_projects/kvpress/logs/pm1_characterized_p23_r3_dc_20261105.log`;
- runner-native terminal marker:
  `KVZAP_PM1_CHARACTERIZED_REPLACEMENT_OUTER_EXIT=<code>`;
- tmux-wrapper terminal marker:
  `KVZAP_PM1_CHARACTERIZED_P23_R3_OUTER_EXIT=<code>`.

The window is independent from RD1 and retains its interactive shell after the
command returns.  It is not joined into the RD1 window.

## Frozen inputs and launch closure

The generated input manifest records:

- accepted DDC SHA-256
  `29215838dc7fe7c2e281f3a9766abbe95add719237eb3e5d62675913c5452326`;
- contextual PM1 child SHA-256
  `dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671`;
- candidate-input manifest SHA-256
  `36ce5058294a74d8f7852e65ce765b1138323978f28d17a0e7f4a899784617fa`;
- replacement Tcl SHA-256
  `7c1e3c70b128925afcd9bd51a38768de7466420757b4a10df68360a2709250ce`;
- runner SHA-256
  `9b4e9601e0ad0abdd5871ff20dde1bd7b9d11a8068caefeaab7475feb902379b`;
- target library SHA-256
  `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d`.

At launch:

- `KVZAP_PM1_CHARACTERIZED_INPUT_PASS` is present;
- `KVZAP_PM1_CHARACTERIZED_STACK_PASS stack_kb=unlimited` is present;
- the r3 runner and native DC process are live;
- the manifest contains the distinct 62,002/62,000 stage gates;
- RD1 remains live in `p16-rd1-dc` with its PID and process tree unchanged;
- approximately 41 GiB memory and 584 GiB filesystem capacity remain
  available.

This is launch/liveness evidence only.  Completion requires native replacement
PASS, both outer exits zero, all stage/register/proxy/clock gates, candidate
DDC and mapped HDL, and complete baseline/candidate/relinked-top native
reports.  Even a pass is a bottom-up characterized diagnostic, not a complete
same-fair-v1 successor result, PPA, external-service-cost, system acceleration
or hardware net-benefit claim.

## Completion update

Mapping, DDC/mapped-HDL generation and all native reports completed, and the
PASS plus both exit-zero markers are present.  Two terminal `SEL-001` errors
from stale collection handles leave two summary cells blank, so clean screen
acceptance is withheld.  The mapped diagnostic shows a 4.201% Page Manager
area reduction but a new -0.005321-ns hold violation.  See
[`dc_pm1_characterized_replacement_r3_result_20261106.md`](dc_pm1_characterized_replacement_r3_result_20261106.md).

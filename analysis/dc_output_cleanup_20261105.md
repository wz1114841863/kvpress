# Remote DC output cleanup — 2026-11-05

## Scope

The active remote output namespaces were reviewed while the RD1 paired DC and
PM1 candidate-child generation continued.  No active output, accepted result,
or older successful record was removed.

Two explicitly failed PM1 selector screens were moved out of the formal
`runs/` namespace into a recoverable failure archive:

| Run | Failure authority | Archived location |
| --- | --- | --- |
| `pm1_selector_screen_20261104_r1` | native DC segmentation fault, outer exit 139 | `/home/yaz80/wz_project/dc_project/kvzap_control_projection/failed_runs_archive/20261105/pm1_selector_screen_20261104_r1` |
| `pm1_registered_selector_screen_20261104_r2` | original side segmentation fault, paired outer exit 1 | `/home/yaz80/wz_project/dc_project/kvzap_control_projection/failed_runs_archive/20261105/pm1_registered_selector_screen_20261104_r2` |

The archive occupies 92 MiB.  This operation intentionally does not reclaim
disk space: it cleans the valid-run namespace while retaining the native logs,
inputs and the r2 banked-side diagnostic reports for later audit.  Permanent
deletion can be considered separately if storage becomes constrained.

## Safety closure

Before moving either directory, both failure markers were rechecked and no
reference from the active remote scripts or workspace was found.  After the
move:

- `dc_feasibility_fair_rd1_shared_20261105_r1` remained present and its DC
  processes remained live;
- `pm1_page_manager_7b34b38_p18` remained present and its firtool process
  remained live;
- tmux windows `kvzap-control-refine:p16-rd1-dc` and
  `kvzap-control-refine:p18-pm1-child-freeze` remained live;
- all older successful runs and artifacts remained in place.

This cleanup changes neither RTL nor experimental evidence.  The archived PM1
runs remain failed diagnostics and must not be treated as accepted mapped
results.

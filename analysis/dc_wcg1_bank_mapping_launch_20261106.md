# WCG1 matched bank mapping/STA launch

Run ID: `wcg1_bank_mapping_sta_20261106_r1`.
Disposition: **launched, not accepted; await user notification of completion**.
Source/tooling commit: `f2b57a9e495953e71b9d6ff26970129580592d3e`.
Scope and acceptance policy:
[`dc_wcg1_matched_bank_mapping_plan_20261106.md`](dc_wcg1_matched_bank_mapping_plan_20261106.md).
Machine-readable input freeze and launch snapshot:
[`dc_wcg1_bank_mapping_launch_20261106.json`](dc_wcg1_bank_mapping_launch_20261106.json).

## Immutable inputs

Remote bundle directory:
`/home/yaz80/wz_project/chisel_projects/kvpress/bundles/wcg1_bank_mapping_sta_20261106_r1/`.
Archive is its sibling `wcg1_bank_mapping_sta_20261106_r1.tar.gz`.

| Artifact | SHA-256 |
| --- | --- |
| Archive | `afb10d4cf6f0c1c801c1c87c684b6a30c3767abb0a92ff9200a3429300ea7990` |
| SHA256SUMS | `feabbb114d3ac41464068a9aabe8044951f1a3d8f4e05a93aec8d5eb89546578` |
| manifest.json | `5f03ffd7ba5897699cc53f9928391137e9ad21a1b1297bd564480071999fde4e` |
| Library DB | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |

Remote archive hash, all eleven frozen files, the actual library DB and all
seven numerical timing/load values passed the launch gates. Generated RTL
matches the locally simulated 64-record pair byte-for-byte. Inputs include
the environment and constraints files rather than depending on the remote
production checkout. No RTL, filelist, archive, process or tmux window belonging
to RD2 was changed or queried in this task.

## Remote execution and observation

- Host: `dc-server`; independent tmux `kvzap-wcg1-map:paired-sta`.
- Pane at launch: `0`, shell PID `23571`.
- Result root:
  `/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/wcg1_bank_mapping_sta_20261106_r1/`.
- Overall log: `<result-root>/launcher.log`.
- Native logs: `<result-root>/reference/native.log` and
  `<result-root>/gated/native.log`.
- Initial observation: reference analyzed/elaborated/linked successfully,
  applied period 2.0 ns with reset timed, and entered Pass 1 Mapping.
  No outer exit marker existed at that snapshot. Size-only preservation
  warning OPT-301 is expected for the deliberately fixed storage architecture.
- Execution is sequential, one DC process at a time, `nice -n 10`, unlimited
  stack. Available memory before launch was 42,111 MiB and disk 582 GiB.

Connect with:

```bash
ssh -t dc-server 'tmux attach -t kvzap-wcg1-map'
```

The `prepare` window retains command-help and preflight evidence; the actual
mapping is in **`paired-sta`**. Native compile output is redirected to the
per-side log, so a quiet tmux terminal is not evidence of completion.

## Completion checks still required

Each side must have `exit_status=0` and its `KVZAP_WCG1_SIDE_RUN_PASS` marker.
The launcher must close both native-exit markers, postcheck PASS,
`KVZAP_WCG1_MAPPING_RUN_PASS_TOOL_INPUT_ARTIFACT_ONLY` and outer exit 0,
plus unchanged input/library hashes. Verify native raw/repaired DDC, mapped
HDL/SDC, area hierarchy and sequential/combinational area, QoR, setup/hold,
gate-enable setup/hold, constraints, lint and actual propagated CKLNQ capture
arcs. Compare both raw area and area after identical hold-repair policy.

Timing failure is a valid negative experiment result, not timing acceptance.
Do not infer area improvement or implementation feasibility from this launch.
This one-bank comparison is not whole-Route-A DC, PPA, physical clock/hold
signoff, external-service cost, system acceleration or hardware net benefit.
No repeated polling or automatic restart is scheduled; the user will notify
when the remote job ends.

# Reconstructed R3 entry_id driver repair — 2026-11-04

## Cause and scope

The compact-membership run's 24 LINT-3 nets and 48 LINT-5 output bits are
reproduced by a small independent design: one coordinate encoder drives two
internal child outputs, while its parent consumes only the handshake.  The
production raw HDL drives both outputs correctly; current parent consumers
do not use entry_id, so DC deletes the unused reconstruction cone but retains
output-to-output aliases without a driver.  This is an internal interface
preservation problem, not evidence that the arithmetic or compact membership
RTL is incorrect.

The repair changes only synthesis treatment and acceptance checks.  Functional
RTL, external ports, latency, ready/valid, authority, publication, admission,
arbitration and membership storage remain byte-for-byte unchanged.  The input
is the same checked 48-file archive, SHA-256
`61d4e51cafea3c96167f371c41b31af051ca5844fd93f58ccba127b681cf7008`.

## Local preservation policy

The explicit policy `r3_entry_id_driver_v1` enables DC 2018's documented
`enable_keep_signal_dt_net` behavior and marks only the 24 nets connected to
the wrapper's authority entry_id result.  Both output carriers share this
result.  It preserves the result's input cone through mapping, without a
new consumer, duplicate record state, whole-parent dont_touch or black box.

The installed tool documentation states that this mechanism prevents unused
input-cone deletion and marks connected logic size_only.  It can affect QoR;
the repaired synthesis policy must therefore be recorded explicitly and its
area/timing measured again.  It is not described as an identical optimization
configuration to the diagnostic run, although all numerical fair-v1
constraints, library, Full-KV input and five proxy boundaries are unchanged.

Disabling boundary optimization on the child and enabling
`compile_preserve_subdesign_interfaces` were independently tested and did not
fix the problem.  Neither broad setting is included in the repair.

The general runner defaults to policy `none`, preserving the old configuration
for historical reproduction.  The dedicated entry-id repair launcher selects
the new policy.  Each run copies the policy Tcl, hashes it in input_sha256.txt
and records the selected policy in synthesis_interface_policy.txt.  The
preservation applies only to the named R3 result nets on the Route-A side.

## Acceptance gate

Before compile, fail unless the implemented wrapper and all 24 result nets
are found.  After compile, check all 48 entry_id output bits with flat
all_fanin startpoints.  An output alias without a driver or a constant tie has
no startpoint and fails this gate.  A passing report must contain
`checked_bits=48 undriven_bits=0` and
`KVZAP_R3_ENTRY_ID_DRIVER_PASS bits=48`.  Native check-design and mapped HDL
must also be inspected for the production design; this targeted gate does not
waive other lint.

## Completed focused validation

The reproducible fixture is under `hardware/route_a/dc/tests/` and uses the
same preservation/check procedures as the production runner.  Remote evidence:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  entry_id_driver_fixture_20261104_r2/
```

Both default and repaired mappings completed.  Default mapping reproduces
24 undriven nets and 48 undriven outputs; the new driver gate rejects it as a
negative control.  Repaired mapping has zero LINT-3/LINT-5 entries and all 48
output bits have real input startpoints.  The run ends with
`ENTRY_ID_NEGATIVE_DRIVER_CHECK_REJECTED`,
`KVZAP_R3_ENTRY_ID_DRIVER_PASS bits=48`, `ENTRY_ID_FIXTURE_PASS`, and pane exit
status zero.  Earlier exploratory directories are retained; only this final
fixture run and the successful mapped simulation are acceptance evidence.

An independent Icarus functional simulation of the mapped standard cells
passes 5,536 vectors: five boundary positions for all 36 layers and eight
heads, plus 4,096 randomized legal coordinates and valid values.  Both
identity outputs and the handshake are checked.  The default mapped netlist
fails the identical testbench as expected.  The LVT functional model SHA-256
is `4aac97c4efda0665cdc8af807a1f5f6706f69a2359453b244562cd8158f27cbf`.
This is functional simulation, with no cell-delay/SDF claim.  Local artifacts
are in `/tmp/kvzap_entry_id_validation_20261104_r1/`.

No Chisel behavioral change was made, so the prior 57/57 source-level
regression and raw-source/proxy closure remain applicable.  The new validation
targets the actual synthesis failure rather than repeating unchanged RTL tests.

## Production verification

The user authorized repair and verification before further optimization.
A fresh paired run will use the dedicated launcher and the same frozen HDL
and numerical fair-v1 inputs.  Full production validation remains pending
until that run emits both side exits, paired/outer pass markers, the new 48-bit
driver report, native check-design, mapped HDL and QoR/timing reports.  The
small fixture does not establish production timing closure or area benefit.

The repair implementation is committed as `2c40d80`.  Its policy Tcl hash is
`a936bd9453002fc3de7f7388aa78c3e74cf31e45a0461773105935ae0157438d`.
Static fair-v1 coverage passed before launch and no older run was overwritten.
The final r2 fixture's mapped netlist was also independently simulated with
the same 5,536-vector pass after the negative driver-gate check was added.

The fresh production paired run is active:

```text
run ID: dc_feasibility_fair_m2p3_entryid_repair_20261104_r1
tmux:   kvzap-control-refine:p11-entryid-dc
log:    /home/yaz80/wz_project/chisel_projects/kvpress/logs/
          entryid_repair_p11_dc_20261104.log
root:   /home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/
          dc_feasibility_fair_m2p3_entryid_repair_20261104_r1/
outer:  KVZAP_ENTRYID_REPAIR_P11_DC_EXIT
```

At launch, the copied Tcl hash and synthesis policy match, the Full-KV native
DC process is active, and no completion marker exists yet.  The window has
remain-on-exit enabled.  Await user notification rather than polling or
starting another run.  Completion inspection must require the 48-bit driver
gate, zero entry_id LINT-3/LINT-5, both side exits, paired/outer markers and
native outputs before accepting the production repair.  Do not start further
structural optimization until this verification closes.

## Production verification result

The paired run later completed normally and is accepted in
`dc_m2p3_entry_id_repair_result_20261105.md`. Both side exits, paired/outer
markers and native artifacts pass. The 48-bit gate reports zero undriven bits,
and LINT-3/LINT-5 are zero. The compact optimization retains an 8.362% mapped
cell-area reduction versus the first refinement, while timing remains blocked
at WNS -0.31 ns. This supersedes the launch-only status above without changing
the frozen functional or claim boundaries.

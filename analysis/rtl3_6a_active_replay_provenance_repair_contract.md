# RTL3.6-A — active replay provenance repair

**Status:** `completed_active_replay_provenance_repair`.

RTL3.6 found that active testbench replay could no longer be revalidated:
two runtime-loaded binding manifests had source-hash drift. RTL3.6-A repairs
only that provenance closure. It neither changes the immutable event schema nor
alters an event owner, carrier, required field, acceptance rule, reference
oracle, testbench-only scope, or functional dataflow.

## Exact active bindings repaired

| Active binding | Drifted source records | Revalidation |
|---|---:|---|
| `rtl2_4_3_attention_terminal_scoreboard_binding.json` | 5 | terminal scoreboard adapter, R4/R6 terminal integration, and result-stub provider suites |
| `rtl2_5_5_active_state_scoreboard_binding.json` | 5 | R5 reclaim, reclaim scoreboard adapter, and active-state integration suites |

The records cover current common navigation/phase documents and current Chisel
sources that evolved after the original binding freeze. The named tests prove
the binding contract remains unchanged: success/fault mapping, exact
identity/status transfer, ready-low atomicity, stale rejection, reset
suppression, durable invalidation-before-free, and global retire acknowledgement.

Historical downstream manifests which merely hash an older binding snapshot
are not rewritten here. They are not active runtime replay dependencies; this
repair refreshes only the two binding JSON files that the Python replay adapters
load and validate directly.

## Restored validation

After the two active hashes are refreshed, the following again passes without
manual bypass:

```bash
.venv/bin/python tools/validate_rtl2_4_3_attention_terminal_scoreboard_binding.py
.venv/bin/python tools/validate_rtl2_5_5_active_state_scoreboard_binding.py
.venv/bin/python tools/validate_rtl2_6_5c_event_capture_replay.py
.venv/bin/python -m pytest -q tests/test_rtl2_6_5c_event_capture_replay.py
```

The RTL2.6.5c replay regains its documented success, fault fail-closed, stale
identity, and bounded ready-low cases. This is still accepted-carrier,
testbench-only replay—not a production waveform, cycle trace, RTL-equivalence
claim, or proof of live cross-language composition.

## Disposition and next boundary

`active_replay_provenance_repaired = true`; however,
`rtl3_functional_realization_complete = false`. RTL3.6-A does not close the
remaining same-instance live functional partial-provider → R4 → R6 terminal →
reclaim path, S2 sidecar ingress, or full-path reset-epoch composition.

The next required closure is `RTL3.6-B — same-instance live functional
provider/terminal composition`. No production-top activation, Python/Chisel
co-simulation, MAC/RoPE/FP RTL, HBM/SRAM/controller realization, timing,
throughput, PPA, model/GPU work, or A4 DSE is authorized.

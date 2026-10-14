# RTL3.9-C4-P0 — frozen event/scoreboard provenance replay contract

## Status and narrow purpose

C4-P0 is complete only when the historical source hashes in the existing
RTL2.4.3 attention-terminal binding, RTL2.5.5 reclaim/retire binding,
RTL2.6.5c accepted-carrier capture/replay manifest, and RTL3.7-C
drain/fault/stall/reset scoreboard manifest replay at their declared immutable
Git commits.  The immutable mapping is
[`rtl3_9_c4_p0_event_scoreboard_historical_provenance.json`](rtl3_9_c4_p0_event_scoreboard_historical_provenance.json).

The frozen records remain byte-for-byte unchanged.  Their `source_sha256`
fields are historical evidence and are replayed with `git show
<frozen-commit>:<path>`; they are not compared with mutable descendant files.
Every declared commit must resolve to its complete ID and remain an ancestor of
`HEAD`.  The validators still check each binding's live semantic schema and
phase-overlay constraints before historical replay.

The testbench Python adapters therefore validate their explicit owner/carrier
and field semantics only.  They do not treat normal later C0--C3b worktree
changes as proof that the frozen RTL2 evidence never existed.  Provenance is
checked explicitly by the C4-P0 validators instead.

## Records and replay commands

```bash
.venv/bin/python tools/validate_rtl2_4_3_attention_terminal_scoreboard_binding.py
.venv/bin/python tools/validate_rtl2_5_5_active_state_scoreboard_binding.py
.venv/bin/python tools/validate_rtl2_6_5c_event_capture_replay.py
.venv/bin/python tools/validate_rtl3_7c_drain_fault_stall_reset_scoreboard.py
.venv/bin/python tools/validate_rtl3_9_c4_p0_event_scoreboard_provenance.py
.venv/bin/python -m pytest -q \
  tests/test_rtl2_4_3_attention_terminal_scoreboard_binding.py \
  tests/test_rtl2_5_5_active_state_scoreboard_binding.py \
  tests/test_rtl2_6_5c_event_capture_replay.py \
  tests/test_rtl3_7c_drain_fault_stall_reset_scoreboard.py \
  tests/test_rtl3_9_c4_p0_event_scoreboard_provenance.py
git diff --check
```

All commands are no-model provenance/semantic checks.  The Python event replay
is still a testbench oracle, not a live Chisel event capture.

## Explicit non-claims and remaining C4 work

C4-P0 does **not** add a scoreboarding tap, manufacture an event, connect a
production top, or demonstrate the C0--C3b path.  It does not close C4 and
does not claim current RTL equivalence, full event coverage, numeric behavior,
functional memory implementation, HBM/SRAM controller or macro behavior,
attention MAC/FP/exp behavior, timing, throughput, area, energy, PPA, model or
GPU execution, or complete LLM inference.

C4-P1 must next audit the event-field provenance and feasibility matrix for
the same-instance C0--C3b path.  Only an actually accepted named owner/carrier
handshake may enter a new event trace; ready-low, stale, mismatch, fault, and
reset traffic must fail closed and emit no invented accepted event.

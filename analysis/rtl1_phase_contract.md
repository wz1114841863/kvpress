# RTL1 — Interface / Control Skeleton Bring-up

**Status:** `authorized_by_gate_rtl0_pass; not_functional_rtl_pass`.

RTL1 may not change frozen owners, ports, assertions, oracles, pruning,
admission, scheduler semantics, page size, S2 count, outstanding bounds, merge
format, or physical realization parameters.

| Phase | Scope | Evidence before advance |
|---|---|---|
| RTL1.0 | Top/all skeletons, ports, reset, ready/valid, SVA/TB/scoreboard attachment | compile/elaboration clean; no behavior claim |
| RTL1.1 | R1 identity/fragment/terminal/reset-init/stale suppression | R1 assertions/oracle tests |
| RTL1.2 | R2 eligibility/FIFO/credit/grant-on-accept | R2 assertions/interleavings |
| RTL1.3 | coupled R3/R5 P3/descriptor/atomic publication | durable-only/one-commit assertions |
| RTL1.4 | S2/direct-pending/four-consumer release | generation/stale/GQA assertions |
| RTL1.5 | R6 lifecycle/terminal/retirement/global drain | authority/terminal/retire assertions |
| RTL1.6 | R4 boundary only | packet/fault binding; no exp/FP RTL claim |

CDC/HBM adapter, macro/port count, physical queues, frequency, timing, PPA,
and speedup remain outside RTL1 and require later implementation/Gate-B evidence.

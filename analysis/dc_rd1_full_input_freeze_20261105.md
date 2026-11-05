# RD1 full paired-DC input freeze — 2026-11-05

## Scope

This freezes the complete control-projection input for the RD1 bank-local
M/S/O member-record read-sharing experiment.  The production HDL delta from
compact-membership commit `7bcd652` consists only of the two files introduced
by RD1 commit `e5d3107`: the M2/P3 wrapper wiring and its combinational shared
reader.  The PM1 selector candidate is not present in this remote production
workspace or generated input.

The accepted synthesis-only `r3_entry_id_driver_v1` policy remains required.
No pruning, admission, R3 publication, R6 authority, R2 arbitration, storage
capacity, Full-KV scope, clock or numerical fair-v1 constraint changes.

## Generated successor and checks

The immutable remote successor is:

```text
/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/
  rd1_shared_e5d3107_p15/
```

The generation provenance records `source_commit=e5d3107` and the same
firtool 1.158.0 executable used by the predecessor flow.  Both source checkers
pass, and an independent post-run audit observed:

| item | result |
| --- | ---: |
| split filelist entries | 48 unique entries |
| aggregate top-level split SV bytes | 451,321,280 |
| ordered source-closure SHA-256 | `4af3a784105d04f12f984204b03f2ef5398bbe199cfa2fd870d35370610cf717` |
| filelist SHA-256 | `5201ba412545e8f0017bd457a899e8caa9d06e9c27425e792eade5420471938d` |
| full generated state | 13,144,071 bits, unchanged from compact membership |
| M2/P3 wrapper state | 400,498 bits, unchanged |
| metadata bridge state | 17,492 bits, unchanged |
| R5 successor checker | PASS |
| control-refinement successor checker | PASS |

The Full-KV SystemVerilog is byte-identical to the compact predecessor, with
SHA-256 `5e4d9918030e3d517d9913ff7c56e2325bd3c1f640e1a844d88a8a4473792256`.
RD1 therefore changes the Route-A read network only; raw state is not an area
or timing result.

## Paired archive and proxy closure

The paired archive contains one Full-KV filelist/source and the 48-entry
Route-A filelist.  The archive also retains checker verification material,
which is not part of either DC filelist.  All five approved same-header proxy
boundaries pass materialization and independent checking:

1. Full-KV S2 payload;
2. Route-A M2 entry;
3. Route-A P3 stage;
4. Route-A R5 availability/generation;
5. Route-A S2 payload/sidecar.

| artifact | SHA-256 |
| --- | --- |
| paired archive | `9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b` |
| proxy manifest | `9a54405e9c2a91ae51bc2b298bf8c40bd86177f87f02f1d72ae3bf59cda341b0` |
| materialization report | `9a63d4dc35d6a83157bb6eb39a3c440e3af07fd4d5f74be7122d1385fe00acbf` |
| independent proxy check | `6f2b2389bcbcc95d7bf77fb1da9bb0f040a7ca6331f73ea35e44bfa82d951bc2` |

The tmux pane `kvzap-control-refine:p15-rd1-freeze` exited zero.  Its initial
outer marker was empty because the launch shell expanded the status variable
too early.  Success is not inferred from that empty marker: all four JSON
reports have `pass=true`, artifact identities were independently recomputed,
and the retained log ends with the explicit successor marker
`KVZAP_RD1_P15_FREEZE_VALIDATED_EXIT=0`.

## Disposition

The input is accepted for one complete paired
`dc_feasibility_fair_v1` run using
`run_rd1_shared_entry_id_repair_dc.sh`.  This freeze does not establish mapped
area, complete Route-A timing, lint improvement, PPA, external-service cost,
system acceleration or hardware net benefit.

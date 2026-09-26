# A4.12.1 — metadata macro/area envelope contract

## Scope

A4.12.1 consumes only the exact self-contained A4.12.0 `_02` report. It
compares exactly three representative metadata/control organizations:

| Candidate | Purpose | Explicit non-result |
|---|---|---|
| M1 | banked SRAM plus a later pipelined-RMW service hypothesis | Does not establish a physical 2R2W macro or a cycle schedule. |
| M2 | duplicated head-control plus pooled quota-accounted queue/staging SRAM | Does not establish replica-coherence cost or throughput. |
| M3 | register-resident head-control hot state plus SRAM backing | Register area is not estimated from CACTI. |

The 8-bank, head-affine, abstract 2-read/2-write/2-RMW requirement remains a
logical service requirement. It is never passed to CACTI as a selected physical
port count. Every CACTI macro is a 1RW RAM proxy.

## Technology boundary

The only technology point is public Hewlett Packard CACTI at `0.032 um`. The
runner records the public source URL, checkout commit, template hash, generated
configs, and raw output. CACTI's area and per-access dynamic-energy values are
analytical proxy values, not a foundry PDK, macro compiler result, signoff
estimate, physical layout, or target process claim.

## Capacity boundary

For each candidate the report separately retains:

- A4.10 logical capacity: local32/shared256/staging512;
- an explicit 36-layer conservative provision mapping for the listed macro
  instances;
- CACTI minimum-array padding; and
- unestimated state, notably M3 register hot state.

Trace peak occupancy is not used to shrink physical provisioning because A4.10
does not establish simultaneous physical layer concurrency.

## Exit

A4.12.1 provides only a metadata SRAM-proxy area envelope and macro-level
characterization inputs. A4.12.2 must separately model access/arbitration/RMW/
scoreboard/commit cycles, sustained issue rate, utilization, queue residence,
commit throughput, and estimated dynamic energy. It cannot reopen A4.8--A4.11
semantics or A4.10 queue parameters.

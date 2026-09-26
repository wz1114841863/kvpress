# A4.12.2 — metadata cycle/service and estimated-energy contract

## Purpose

A4.12.2 is the final metadata/control execution-cost step.  It consumes the
accepted A4.12.0 interface inventory, A4.12.1 `_03` public-CACTI macro
envelope, A4.10 `_04` queue contract, and A4.9.2 record-granular trace chain.
It does not create a queue, execution-granularity, scheduler, pruning,
admission, or transaction-semantic variant.

The fixed workload replay is only:

```text
HA8-wide + head-affine 8 banks + record-granular internal execution
+ local32/shared256/staging512 + existing single group commit boundary
```

## Declared physical-service mappings

One service-model cycle is a declared arbitration/access coordinate.  It is
not derived from a clock target or CACTI access time.

| Candidate | Declared mapping | Access-accounting boundary |
|---|---|---|
| M1 | One 1RW metadata SRAM proxy per bank; every `head_control` and `span_owner` operation competes for that bank slot. RMW holds it for two service cycles. | One read, write, or read+write respectively, charged to A4.12.1 persistent metadata macro pJ/access. |
| M2 | Two 1RW `head_control` replicas plus one 1RW `span_owner` SRAM proxy per bank. Head reads select one free replica; head writes/RMW update both replicas atomically in this model. | Mirrored head writes/RMW charge two replica writes. Span accesses use its own A4.12.1 macro proxy. |
| M3 | `head_control` uses two declared hot-register service slots per bank; `span_owner` uses one 1RW SRAM proxy. | Register accesses are counted but deliberately excluded from energy because A4.12.1 did not estimate register energy. Only span-SRAM accesses receive CACTI pJ/access. |

Final publication remains the sole existing group commit boundary.  A4.9.2
HA8-wide has no declared commit-slot serialization (`commit_slots=0`), so every
group whose members and predecessors are complete may publish in the same
service-model coordinate.  A4.12.2 does not invent a global commit controller,
commit-port count, or physical contention.  The reported commit rate is an
observation of this frozen semantic replay, not an implemented commit
throughput.

## Outputs and boundaries

For every frozen context/candidate, report drain, modeled cycles, latency
coordinates, sustained issue rate, resource utilization, queue residence,
semantic commit publication rate, macro access counts, and estimated SRAM
dynamic energy.

CACTI ns values remain macro characterization fields.  CACTI pJ/access times
the counted accesses is an **estimated SRAM dynamic energy**, excluding M3
register energy, arbitration, scoreboard, commit, wires, clock, leakage,
physical layout, and payload-path cost.  It is not measured energy or PPA.

An unfavorable outcome enters the A4.12.3 metadata-side partial ledger; it
cannot reopen A4.8--A4.11 or the A4.10 contract.

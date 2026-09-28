# A4.14.1 — Route-A accounted net-benefit ledger and decision contract

## Purpose

A4.14.1 closes the research DSE with one evidence-classified ledger. It joins
the accepted payload action/cost reports with A4.14.0's same-workload M2
binding. It introduces no new queue, execution, macro, page, source-buffer,
payload, scheduler, pruning, admission, or controller candidate.

```text
exact external-storage lifecycle
  -> logical cold removal / packed resident accounting
  -> fair Full-KV and Route-A legal-GQA traffic accounting
  -> declared payload service and dynamic-energy proxy
  + workload-aligned M2 control-entry access proxy
  -> omitted-cost budget and conditional disposition
```

## Cost classification

| Class | Treatment |
|---|---|
| Common baseline infrastructure | S2's two-page source-buffer proxy area is reported once as shared Full-KV/Route-A GQA infrastructure. Its path-specific dynamic accesses remain charged on each side. |
| Route-A fixed provision | M2's public-CACTI proxy area is reported once and never multiplied by workload. |
| Route-A unphysicalized provision | P3's 1,179,648-B staging capacity, packed-page management, sidecar storage and partial-state interface remain listed but receive no invented area or energy. |
| Workload-dependent cost | Fair payload HBM/source-buffer proxy energy and explicit M2 head/span access proxy are reported per request and per observed attention position. |
| Unestimated differential cost | M2 queue/staging dynamic accesses, P3 stage energy, sidecar latches, merge arithmetic, partial-state RF/SRAM/spill, controller/interconnect, clock/wire/leakage and HBM physical area remain explicit. |

The M2 fixed proxy includes pooled queue/staging macro area, but A4.14.0 has
no queue/staging SRAM access mapping. Its M2 dynamic result is therefore a
**control-entry-only** CACTI proxy, not total M2 dynamic energy.

## Accounting boundary

For each workload report request absolute values, values per observed attention
position, and Route-A/Full ratios. The benefit chain retains an evidence class
at every step:

```text
logical matured-cold removal       (software observation)
  -> packed resident capacity      (deterministic accounting)
  -> fair-GQA transferred bytes    (deterministic accounting)
  -> payload service coordinate    (declared target model)
  -> accounted dynamic energy      (declared HBM plus CACTI proxy composite)
```

Let `B = E_full_accounted - E_route_accounted`, where Route-A includes only
explicit payload/P3/source-buffer values plus A4.14.0's M2 control-entry
proxy. Route-A preserves the accounted energy sign precisely when:

```text
E_route_unestimated - E_full_unestimated < B
```

`B` is an engineering omitted-cost budget, not a prediction that omitted
modules cost zero. Payload and metadata service coordinates remain separate
and are never added into total cycles or latency.

## Disposition

The engineering HBM gate is `Route-A total modeled HBM bytes including P3 <=
0.5 * Full-KV fair HBM bytes` for every workload. Two is an engineering margin
for omitted costs, not a natural-law threshold.

Conditional go requires exact guards, lossless M2 drain, this HBM gate, and a
positive `B` for all workloads/profiles. It does not establish physical PPA,
measured speedup, final chip area or real-controller readiness. A pass ends
research DSE; the next activity is architecture specification, not A4.14.2.

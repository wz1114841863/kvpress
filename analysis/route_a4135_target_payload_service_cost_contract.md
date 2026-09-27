# A4.13.5 — target-profile payload service and cost DSE contract

## Purpose

A4.13.5 maps the accepted A4.13.4 page-source action interface to one declared
primary payload-service profile and one one-factor bandwidth sensitivity.  It
compares only the fair paths already fixed by A4.13.3/4:

```text
Full-KV + legal four-head GQA reuse
Route-A packed + legal four-head GQA reuse
```

It does not alter masks, page size, P3 admission, GQA grouping, source
lifecycle, A4.10 queues, metadata service, or execution semantics.  No extra
payload/cache/scheduler/pre-fetch candidate is introduced.

## Exact inputs and target-service proxy

The inputs are the accepted A4.13.3 and A4.13.4 reports, with SHA-256
`fea9780d44238f5128008793a12e605e411a95355eaa44e4ad6f71f8b6a735f1` and
`2390958f801c63b7a54e725106b9e75bd36de8950b733ab9bac9d4ac2ee94597`, plus
the tracked `hardware/route_a/payload/a4135_target_profiles.json`.

The profile calls 64 B a **modeled HBM transfer transaction**.  This is a
declared controller-proxy granule, not an assertion about a native HBM
protocol command, burst, pseudo-channel, interleave, or vendor device.  The
primary has four modeled transactions/cycle (256 B/cycle); the sole sensitivity
has two (128 B/cycle).  Every other latency, consumer-rate and energy
coefficient is identical.

Read/write energy coefficients are declared profile inputs.  They create an
estimated dynamic-energy ledger, not a measurement.  No HBM physical area is
estimated.

## Source-buffer physical proxy

Each 32 KiB payload page buffer is represented by one explicit public-CACTI
proxy macro: 128 entries x 2,048 bits, one read-write port, public 32 nm
proxy node.  It has 128 writes per packed/full page fill and 128 multicast
reads per page consumption, independently of four query-head consumers.  A
single read is broadcast by the datapath; four CACTI reads are not charged.

S1 uses one macro.  S2 uses two identical macros; fill and consume may overlap
only because they occupy separate page buffers.  This is not a multiport SRAM
claim.  The 512-B sidecar and 2,080-B pipeline-local partial state retain the
A4.13.4 status `unestimated_without_physical_implementation`.

## Cycle and overlap model

For a packed page, `T_fill` includes one profile read startup plus transfer of
32 KiB payload and 512-B sidecar.  `T_consume` consumes 128 internal 256-B
beats at the profile consumer rate.  Per stream:

```text
S1 = N * (T_fill + T_consume)
S2 = T_fill + (N - 1) * max(T_fill, T_consume) + T_consume
```

S2 fully hides a next-page fill exactly when `T_consume >= T_fill`; warm-up,
drain, and fill-caused consumer stalls remain included.  Direct hot/pending
source traffic and P3 admission traffic are separately mapped to the profile
transfer service; their physical issue ordering is not observed.

## Evidence boundary

CACTI values are public SRAM proxy estimates.  HBM transactions, cycles,
energy, source-buffer utilization and stalls are declared target-profile model
results.  This stage does not measure HBM traffic/bandwidth/latency, choose a
real controller or macro, estimate HBM area, implement attention arithmetic,
or establish end-to-end performance, architecture readiness, or RTL.


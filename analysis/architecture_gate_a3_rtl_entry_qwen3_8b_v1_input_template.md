# Superseded `rtl_entry_qwen3_8b_v1` deployment-input template

**Status:** retained decision/provenance navigation only.  Its unresolved
fields were closed by the selected
`architecture_gate_a3_rtl_entry_qwen3_8b_32k_s1_v1.json` profile.  Neither
document is an RTL authorization.

The following former placeholders explain the selected values; they were not
copied from A4 workload maxima.

```text
MAX_CONTEXT_TOKENS = 32768
MAX_CONCURRENT_SEQUENCES = 1
MAX_PENDING_RESIDENT_RECORDS = (32768 - 128) * 1 * 36 * 8 = 9,400,320
MAX_LIVE_PENDING_TRANSACTIONS = 1
MAX_LIVE_READ_REQUESTS = 4 = 2 S2 fills + 1 endpoint + 1 packing read
MAX_LIVE_WRITE_REQUESTS = 1 = one packing write
MAX_LIVE_SOURCE_GROUPS = 1 = one KV-head-group engine
TOTAL_COLD_KV_HBM_POOL_BYTES = 5 GiB shared pending/packed address pool
CORE_DATA_W / response_fragment_width = 512 bits / 64 B
logical retirement owner = external runtime/session manager
physical reclaim owner = KV subsystem after quiescence
```

The frozen anchor fields remain `NUM_LAYERS=36`, `NUM_KV_HEADS=8`,
`HOT_WINDOW=128`, `MAX_PACKED_PAGE_POPULATION=64`, 512-B K+V payload/token,
and 8-B position sidecar/token.  The profile uses a keep-all cold capacity
guard and one migration-page reserve; it does not assume observed KVzap
compression.  The 5-GiB address pool is an interface-capacity choice, not a
physical-HBM, PPA, latency, or throughput claim.

# RTL3.5-C — cross-language functional partial-packet binding

**Status:** `implemented_static_cross_language_packet_binding_pre_production_top`.

RTL3.5-C closes the narrow binding deferred by RTL3.5-B.  It proves that one
versioned output packet from the pure-software
`route_a_functional_attention_partial_provider` is accepted byte-for-byte by
the existing Chisel structural path:

```text
Python RTL3.5-B fixed query/source lease
  -> static versioned fixture (identity + source instance + header + 8 words)
  -> route_a_source_service_packet_adapter
  -> route_a_merge_boundary structural acceptance
  -> consumer_partial_commit
```

The shared resource is
`hardware/route_a/chisel/src/test/resources/rtl3_5c_functional_partial_packet.fixture`.
Its one deliberately small positive witness freezes hot source kind `0`,
request identity `(6, 0)`, source instance `(0, 10, 1)`, consumer `2`, one
present 128-bit header, and eight ordered 512-bit fragment words.  The Python
test regenerates these exact fields from the RTL3.5-B functional provider;
the Scala directed test consumes the same resource and proves the existing
adapter/R4 path emits the matching `consumer_partial_commit`.

## What is, and is not, bound

The fixture is an immutable interchange record, not a runtime foreign-function
interface.  It proves numerical packet bytes are not silently reformatted,
reordered, or associated with a different identity/source/consumer at the
already-existing structural acceptance boundary.  The Chisel test still uses
the normal R6 source plan and availability facts before the hot offer is
accepted.

It does not bind `route_a_kv_subsystem_top`; create a production source
payload transport; implement Q/K/V, RoPE, attention MAC, exp, FP pipeline, or
R4 numeric RTL; select an issue schedule; complete all four consumers; or
claim timing, throughput, PPA, HBM/SRAM/controller realization, model/GPU
evidence, or a new A4 DSE.  In particular, it is not cross-language live
co-simulation and does not make the Python provider a Chisel module.

## Fail-closed interpretation

Only the exact fixture is a positive witness.  Existing adapter checks remain
the controlling Chisel behavior for malformed header fields, wrong request or
incarnation, source-instance/generation mismatch, consumer mismatch, fragment
index/last mismatch, and ready-low backpressure.  RTL3.5-C changes none of
those contracts and adds no fallback: a nonmatching packet cannot create a
commit, release, terminal, authority transition, or Full-KV substitution.

## Validation

```bash
.venv/bin/python -m pytest -q \
  tests/test_rtl3_5b_functional_attention_partial_provider.py \
  tests/test_rtl3_5c_cross_language_packet_binding.py \
  tests/test_rtl3_5c_cross_language_packet_binding_manifest.py
.venv/bin/python tools/validate_rtl3_5c_cross_language_packet_binding.py
cd hardware/route_a/chisel && sbt -batch \
  'testOnly kvpress.routea.rtl2.RouteASourceServicePacketAdapterSpec'
```

Evidence labels: static cross-language packet-binding test; no model/GPU; no
cycle/timing/throughput claim; no PPA claim; no RTL numeric-correctness claim;
no production-top activation; no new A4 DSE.  Exact source binding is frozen
in [`rtl3_5c_cross_language_packet_binding_manifest.json`](rtl3_5c_cross_language_packet_binding_manifest.json).

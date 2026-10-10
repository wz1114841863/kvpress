# RTL3.7-C — C2 drain membership and event-scoreboard closure

**Status:** `completed_testbench_only_c2_drain_fault_stall_reset_scoreboard`.

RTL3.7-C closes the bounded C2 membership gap left deliberately outside
RTL3.7-B. A testbench-only joiner waits for both the publication R1/R2 wrapper
and the separately-bound C2 R1/R2 wrapper to assert each same logical status
(`mem_init_done`, R1 drain, R2 payload drain, R2 descriptor drain), then emits
one existing status into the unchanged R6 collector. It introduces no status
code, production top wiring, controller, or physical implementation.

The same-instance witness also records only observed handshake facts in a
host-side event scoreboard:

```text
R3 payload durable -> source plan accept -> C2 request held ready-low
-> S2 READY -> C2 release accepted -> attention terminal accepted
-> runtime retire accepted -> retire_ack accepted
```

Directed coverage includes: (1) three-cycle legal C2 memory backpressure with
the request held losslessly; (2) reset plus old-epoch C2 response suppression
before both R1 wrappers reinitialize; and (3) inherited typed packed endpoint
fault tests, where a terminal fault cannot make S2 READY or deposit payload.

This remains testbench-only evidence. C2 grants, C1 sidecar fixture transport,
and static functional partial/R4 fixtures remain explicitly unclosed. No
deadlock, timing, throughput, PPA, production RTL, model/GPU, or new A4-DSE
claim is made.

## Validation

```bash
cd hardware/route_a/chisel
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "retains event order"'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteARTL265eSameInstanceWitnessSpec -- -z "rejects a stale C2 response"'
env JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
  sbt -batch 'testOnly kvpress.routea.rtl2.RouteAPackedS2ReadPathSpec -- -z "fault"'
cd ../../..
.venv/bin/python tools/validate_rtl3_7c_drain_fault_stall_reset_scoreboard.py
.venv/bin/python -m pytest -q tests/test_rtl3_7c_drain_fault_stall_reset_scoreboard.py
```

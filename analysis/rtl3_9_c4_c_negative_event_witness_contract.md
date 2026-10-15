# RTL3.9-C4-C — negative accepted-event witness

## Status

C4-C is complete as a narrow same-instance C3b testbench witness. The directed
Chisel run passed all three named negative tests (SBT exit code 0, 2026-10-15).
It uses the C4-C precondition audit's four case rules and appends a host-only
trace record only after an actual selected C4 event handshake. It adds no RTL
state, event owner, event FIFO, retry, or fallback.

## Cases

`stale_r1_read_response` holds the already accepted authority prefix, offers a
non-matching R1 response, keeps S2 FILLING, and permits no terminal, page-free,
or retire-ack event. `stale_or_mismatched_r4_completion` offers a wrong request
result and a wrong-incarnation numeric fault while one exact R4 merge work is
outstanding; neither input is accepted and neither creates an event.

`matching_r4_numeric_fault` then supplies the exact R4 fault for that issued
work. It permits exactly one fault-valued terminal after the authority record;
the test holds that selected terminal ready-low before accepting it, and
forbids terminal replay, page-free, and retire acknowledgement. Finally,
`reset_while_selected_event_is_held` resets while authority is valid and
ready-low, requiring every C4 event output to remain invalid without fresh
initialization.

## Boundary

This is functional testbench evidence only. The named functional memory,
partial provider, and R4 reference remain explicit outer environments. It does
not establish a controller/macro, HBM/SRAM, attention MAC, FP/exp pipeline,
timing, throughput, area, energy, PPA, model/GPU result, or complete
inference.

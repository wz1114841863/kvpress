# Gate-RTL0.3 — assertion, scoreboard, and coverage closure

**Status:** `complete_non_implementational_assertion_planning; rtl_entry_review_pending`.

The machine-readable matrix is `rtl_entry_assertion_matrix.json`.  It binds
the frozen owner and port contracts to property intent, reference-scoreboard
ownership, directed tests, fixed-seed randomized scenarios, environment
assumptions, and coverage bins.  It is not SVA source, RTL, a formal proof,
or a timing/performance claim.

Scoreboard ownership follows the architecture owners: lifecycle checks
authority/terminal/retire; R1 checks identities/fragments/reset; R2 checks
FIFO/credit/grants; S2/direct checks generation/release; R3/R5 checks atomic
publication/descriptor reclaim; R4 checks packet/order/fault against the
existing Python reference.  The future RTL testbench may call these references
as golden scoreboards but may not change their semantics.

Environment assumptions constrain only progress: accepted external requests
eventually complete, consumers eventually accept, and named drain members
eventually acknowledge.  DUT safety guarantees never depend on those
assumptions.  Progress records use finite proof depth/fairness stimulus chosen
by the verification environment; they establish no latency or throughput.

| ID | Kind | Owner | Property intent | Environment assumption | Coverage |
|---|---|---|---|---|---|
| a_descriptor_unique_memory_path | safety | R1 | no alternate memory path | adapter protocol | payload/sidecar/descriptor |
| a_metadata_publish_commit | safety | R3 | prerequisites before publish | none | missing prerequisite subsets |
| a_ready_low_nonmutation | safety | R2 | stable on ready-low | arbitrary ready-low | every bundle |
| a_descriptor_invalidate_before_free | safety | R5 | durable invalidation before free | progress only | generation/wrap |
| a_numeric_fault_consumer | safety | R6 | one post-GQA terminal fault | none | source/fault timing |
| a_reset_stale_exclusion | safety | R1 | stale cannot mutate | init suppression | stale classes |
| a_global_retirement_membership | safety | R6 | all drain members before ack | progress only | withheld member |
| a_authority_conservation | safety | R6 | one authority | none | hot/pending/packed/DROP |
| a_fifo_credit_losslessness | safety | R2 | ordinal/credit conserved | none | classes/credits |
| a_gqa_release | safety | S2 | four commits before release | none | consumer IDs |
| a_stale_response | safety | R1 | old identity no mutation | none | S2/direct |
| a_exactly_one_terminal | safety | R6 | one terminal/no fallback | none | ok/fault/retire |
| p_accepted_to_terminal | progress | R6 | accepted eventually terminal | memory + consumer fairness | terminal paths |
| p_retire_to_ack | progress | R6 | retire eventually ack | completions + drain fairness | drain combinations |
| p_credit_return | progress | R2 | credit eventually returns | terminal fairness | terminal credit paths |

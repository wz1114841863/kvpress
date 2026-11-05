# PM1 Page Manager successor generation result — 2026-11-05

## Disposition

`pm1_page_manager_7b34b38_p18` ended cleanly as a failed input-freeze gate,
not as an accepted successor:

- the tmux window closed and no generation/firtool process remains;
- CHIRRTL emission passed;
- firtool produced non-empty split Verilog;
- exact Page Manager port identity failed;
- the outer marker is
  `KVZAP_PM1_PAGE_MANAGER_P18_GENERATION_EXIT=1`;
- neither `KVZAP_PM1_PAGE_MANAGER_PORT_IDENTITY_PASS` nor
  `KVZAP_PM1_PAGE_MANAGER_SUCCESSOR_PASS` exists;
- `input_sha256.txt` and `split_files.txt` were intentionally not emitted
  after the failed gate.

No DC command was invoked.  The failed output must not be used by the planned
saved-DDC child replacement.

## Generated artifacts before the gate

- candidate CHIRRTL: 465,435,467 bytes;
- candidate Page Manager split SV: 319,895,002 bytes;
- split R5 availability-array dependency: 101,330,882 bytes;
- frozen baseline Page Manager split SV: 330,453,081 bytes.

These are source/text sizes only.  In particular, the smaller candidate SV is
not mapped-area evidence.

## Root cause

The standalone candidate emitter changes lowering context.  In the frozen
paired top, `route_a_page_manager` is a child of the real measurement parent,
so firtool removes bundle fields that the parent does not consume.  When
`RouteAPageManager` is emitted as the standalone top, those top-level fields
must remain externally visible.

The normalized headers confirm this diagnosis:

- frozen contextual child: 144 ports, 146 header lines;
- standalone PM1 top: 218 ports, 220 header lines;
- candidate-only additions: 74 ports;
- baseline ports missing from candidate: zero.

The added ports are unused portions of the reclaim/append candidate records,
allocator release, descriptor-maintenance terminal, status fields and related
typed bundles.  This is not a module-name formatting mismatch and must not be
bypassed with `change_link -force` or an ad-hoc pin map.

## Required successor

The next generation attempt must instantiate the PM1 Page Manager under the
same real `RouteAMeasurementDut` parent and full synthesis profile as the
frozen paired input, then extract `route_a_page_manager_pm1` from that
contextual split output.  The selector-enable parameter must remain optional
and default false so accepted inputs and the active RD1 run are unchanged.

Only after exact contextual port identity, non-empty artifacts and hash
closure pass may the characterized saved-DDC replacement screen begin.

The separate RD1 paired DC remained live throughout this inspection and was
not modified.

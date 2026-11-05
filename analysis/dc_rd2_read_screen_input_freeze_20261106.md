# RD2 isolated read-network input freeze — 2026-11-06

## Accepted comparison

The user-authorized next RD2 gate is one matched small-synthesis comparison.
Both sides retain the same RD1 M/S/O shared member reader and full 36 x 64
member/suffix input image.  Only C/F/B member-field and M/C suffix-read
realization differs.  Four remaining raw readers stay observable with valid
low; no mutually exclusive C/F/B assumption is used.

Input authority is the completed p26 remote validation from source `48f8cf3`:
two tests pass at 4 x 8 and 36 x 64, with exact paired-port identity.  The
small screen excludes storage cost and does not switch production RTL.

Prepared immutable root:
`/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs/rd2_read_network_screen_20261106_r1`.
It contains copied RTL, scripts, accepted test manifests/XML and five source
files, with no symlink dependency on a mutable source workspace.

## Input and static closure

Nine pinned inputs/scripts/manifests rehash exactly; five Scala source files
match the accepted p26 source manifest; XML reports two tests and zero
failures/errors/skips; paired module headers are independently equal.

| artifact | SHA-256 |
|---|---|
| RD1-enabled baseline SV | `f8080b6d97ab82d2aeed309774cc64e2481b0552a34c78d3c7d1079d6346fb1f` |
| decoded candidate SV | `caf0f8cf9c3b05e05e748386d560a4574fe715359ef2546ba368c06a4261280c` |
| runner | `42f8ca39adf6cd421ce0678b4addd3419f6bb0f2a9bf5f6145d3b1c14b706c37` |
| screen Tcl | `4b15314ee461985a8ec35d3b75708a27c75fe7675a3b14bf70c761c32456705c` |
| constraint Tcl | `3bc9d0e4b3caf9244f38e265ad1222f2ea36d89bed0a31d27a4d3cba19fe5007` |
| fair-v1 profile | `1de09887b99e78bf66355385e30b841c73cc24891cbb2bec0b49311710d2598d` |
| environment | `5439a78c063480bb9be1a4583929da3d2bf147101a884242f62dbad27c3fb8e4` |

The same fair-v1 numerical profile is retained: period 2.0 ns, setup/hold
uncertainty 0.10/0.02 ns, input/output delay 0.20 ns, input transition 0.05 ns
and output load 0.005 pF.  The runner verifies the library/constraint hashes
and numerical environment again at native launch.  Bash syntax, runner help,
Tcl structural completeness and `git diff --check` pass.

Each side runs in a separate DC process at medium effort with unlimited
stack.  Postcheck requires both native exits zero, both side PASS markers,
no native Error/Fatal, zero registers and complete reports/DDC/mapped HDL.
The input hashes are rechecked after both compiles.  Area, precision path
delay/slack, setup/hold, fanout and lint are separate inspection outcomes.

## Integration scheduling

RD1+PM1 still needs a complete integrated same-fair-v1 paired DC before it
can become an accepted cumulative top.  The current user action launches only
RD2 small synthesis.  The recommended sequence is to inspect RD2 first, then
choose RD1+PM1 alone if RD2 is rejected, or prepare an independently verified
RD1+PM1+RD2 successor if RD2 merits integration.  Do not add PM1's bottom-up
area saving arithmetically to the RD1 result or assume timing/hold closure.

RD2 production integration still requires its out-of-range/continuous-ready
gate, functional regression and full generated-input closure.  No complete
paired DC or additional architecture change is launched by this freeze.

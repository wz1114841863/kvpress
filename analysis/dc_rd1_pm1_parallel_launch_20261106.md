# RD1+PM1 complete paired DC preparation

Authorization: freeze RD1+PM1, launch complete paired DC in independent tmux,
and develop WCG1 wrapper isolation in parallel. RD2 is excluded. This snapshot
records preparation, not native launch/result acceptance.

The new input composes immutable accepted RD1 raw RTL with the exact PM1 child
from the real-parent contextual p19 export. Only the child module declaration
is normalized from `route_a_page_manager_pm1` to `route_a_page_manager`;
its 144-port header must match exactly. All other 47 Route-A compilation units,
Full-KV and both filelists remain byte-identical to the frozen RD1 archive.
The archive itself and every compiled member are checked before copying.
The PM1 child SHA remains the accepted `dfaf40814b...96671` full pin in the
freezer. This is accepted-component composition, not new Chisel export or a
claim of a newly executed full functional suite.

Generated-source gates retain 48 files, 16 typed top-port families, 12 real
control owners and all state capacities. R5 and control-refinement source
checks, per-module state-bit/object identity, five paired typed-array proxies,
archive/library/manifest hashes and static timing coverage must pass before
the script starts DC. A failure stops before synthesis. All real parent
controllers remain present; no PM1 saved-DDC replacement is used here.

The full paired run retains `dc_feasibility_fair_v1`: 2 ns, setup/hold
uncertainty 0.10/0.02 ns, I/O delay 0.20 ns, transition 0.05 ns, load 0.005;
the constraint Tcl, library, entry_id driver preservation and 1/48 filelists
retain the accepted policy. There is no WCG1 or RD2 in this comparison and no
new clock/hold repair policy. PM1's known local hold failure and RD1's setup
failure are open measurement outcomes; a native exit 0 will not close timing.

`run_rd1_pm1_freeze_and_dc.sh` and `freeze_rd1_pm1_input.py` are separately
frozen with copied DC scripts, leaving shared server workspaces/scripts and
earlier results unchanged. The independent session is planned as
`kvzap-rd1-pm1:paired-dc`, run ID
`dc_feasibility_fair_rd1_pm1_20261106_r1`. The freeze/compile log will be
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/rd1_pm1_full_dc_20261106_r1.log`.
All long work uses tmux and unlimited stack; one native DC side runs at a time.

WCG1 is developed only after freezing these inputs. Its default-off wrapper
candidate must keep both raw record tables, separate member/suffix write
enables, exact reset behavior, all readers and admission/authority/binding
handshakes. It needs real-wrapper differential/regression evidence and later
propagated-clock setup/hold tests at 2 ns; the single-bank positive result
does not grant production integration or a full WCG1 DC launch automatically.

Every run completion still requires both side/native/outer markers, input
rehashing, mapped artifacts, native area hierarchy, precision timing, proxy
and 48-bit entry_id driver closure. No PPA, service zero-cost or system/net
hardware-benefit claim is authorized.

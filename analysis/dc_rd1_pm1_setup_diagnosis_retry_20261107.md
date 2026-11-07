# Saved-DDC setup diagnosis: r1 failure and corrected r2

The completed `rd1_pm1_setup_diagnosis_20261107_r1` is **failed tooling**, not
a completed timing diagnosis. Native RD1 exit 1 and outer persisted exit 1
agree. RD1+PM1 was never started; no QoR, timing, area or endpoint reports
were emitted. Both mapped inputs remain immutable.

After reading/linking RD1, DC 2018 returns an absent `propagated_clock`
attribute on the saved ideal clock (`UID-101`). The script then evaluates
the returned empty string as a Tcl boolean and aborts. This is a checker
bug: an absent dynamic attribute is not a design-timing failure. The native
log SHA is `50a97f854f841d1744a15d9a45bccc3618e695ec4f3d60e157902b8e1dc50eae`.
Fresh hashes verify the frozen r1 Tcl, RD1 DDC and target DB. Original r1
files/statuses remain preserved; its earlier launch JSON is not rewritten.

The successor removes that attribute query. It first writes native
`report_clock -attributes -skew -nosplit` and positively checks the actual
saved clock row: name, 2.00-ns period, {0 1} waveform, source {clock}, and
empty attributes. A propagated clock, hold-fix flag, missing row, changed
period/waveform or source fails. This reads the saved clock policy; it does
not set an ideal clock or alter any saved timing constraint.

Eight ordinary-Tcl parser regressions pass, including ideal/wrapped rows
and six negative cases. Shell syntax and read-only scope checks pass. All
other native diagnostic commands, DDC/library pins and the runner remain
unchanged. The new immutable r2 must still produce both native exits, clean
native/redirected reports, full input rehashes and outer exit 0 before any
STA result is accepted.

Existing full-run top-20 evidence still shows six direct PM1 reclaim-selector
paths and independent cross-owner ready/request chains. It does not provide
the old selector's precise margin or the TNS partition. Therefore no final
PM1 repair priority or WCG1 integration baseline can be accepted yet.
Neither a PM1 RTL repair nor full WCG1 paired DC is started by this correction.

The separate JSON freezes failed-r1 evidence, exact r2 source hashes,
immutable output/session/log identifiers and observed startup. The retry is
read-only saved-DDC STA in an independent tmux, with unlimited stack and at
most two cores; it is not a new synthesis. Notify the user on launch and
await their completion notice, preserving all earlier results.

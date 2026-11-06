# WCG1 real-wrapper functional validation launch

Run ID: `wcg1_wrapper_82bd953_20261106_r1`.
Status: remote source/Test compile PASS; functional completion pending.
Implementation commit: `82bd953179e7d6d09ff1227c557f8ccaf3e7acd3`.
Contract and open timing/integration gates:
`dc_wcg1_wrapper_isolation_20261106.md`.
Exact source manifest: `dc_wcg1_wrapper_functional_launch_20261106.json`.

The new independent tmux is `kvzap-wcg1-wrapper:functional`.
Its log is
`/home/yaz80/wz_project/chisel_projects/kvpress/logs/wcg1_wrapper_functional_20261106_r1.log`.
Workspace/result root is
`/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/wcg1_wrapper_82bd953_20261106_r1/`.
The separate source archive is in the sibling bundles directory.

Source archive SHA-256:
`acae22189e4b254c95316101f262d0f6e122dac5290de43981ce35f47ddb1f15`.
Runner SHA-256:
`5f84e073d1f850006745c1b84dd51d38f450cca6b8e4573bb40027b00dc14a0f`.
All 122 source files are frozen under a new workspace; the three RD2
helper/spec/emitter files and old generated artifacts are excluded.
No shared workspace, old input or current RD1+PM1 archive is modified.

Initial remote gates pass the archive hash and memory preflight; 40,896 MiB
was available before launch. The job uses native Java 11, a 3-GiB JVM,
two active JVM processors, unlimited stack, one C++ build job and two
Verilation jobs. `KVZAP_WCG1_WRAPPER_INPUT_PASS` is present. Remote
`Test / compile` completes successfully in 42 seconds; no functional PASS
or outer exit is inferred from that source build.

The job then runs the four-case baseline suite and four-case WCG1 real-wrapper
reference miter. Candidate geometry is 36 x 64 x (79+80), with all ready/valid
outputs compared continuously and live payloads compared under their channel
valid. The ordinary Tcl/Scala compile and native clock-gate model checks are
preparation evidence only; no EDA tool or WCG1 synthesis/STA is launched here.

After user completion notification, require both four-case XML reports with
zero failures/errors/skips, `All tests passed.`, unchanged source/archive
hashes, `KVZAP_WCG1_WRAPPER_POSTCHECK_PASS tests=8`,
`KVZAP_WCG1_WRAPPER_FUNCTIONAL_RUN_PASS`,
`KVZAP_WCG1_WRAPPER_VALIDATION_OUTER_EXIT=0` and exit_status=0. Keep failed
inputs/logs and locate the failure before any retry. Directed simulation
does not close universal generic equivalence or real-parent gate setup/hold.

The separate `kvzap-rd1-pm1:paired-dc` full run continues from its earlier
immutable input. WCG1 edits cannot enter it. Do not launch a combined
WCG1+RD1+PM1 full run before the remaining functional/generated/native-clock
gates. The 2-ns constraint is retained for any later matched STA; no physical
hold, PPA, service cost, speedup or hardware net-benefit claim is made.

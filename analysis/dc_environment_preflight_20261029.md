# DC environment preflight — 2026-10-29

**Status:** `environment_available_dc_configuration_not_started`.

This is the first bounded prerequisite after the paired generated-HDL freeze.
It records server capability and adds a read-only preflight; it does not run
DC or select timing, memory, macro, numeric, external-service, or PPA policy.

## Verified remote availability

| Item | Observed value |
| --- | --- |
| Host | `ercesi413` (`dc-server`) |
| DC executable | `/opt/synopsys/dc2018/O-2018.06-SP1/bin/dc_shell` |
| DC version command | `O-2018.06-SP1`, build date 2018-07-19 |
| PDK root | `/home/yaz80/wz_project/dc_project/pdk/TSMC28` |
| Standard-cell DB candidates | LVT/ULVT L30 and LVT L35, all SSG 0.81 V / 125 C |
| Existing inherited feasibility default | `tcbn28hpcplusbwp12t30p140lvtssg0p81v125c.db` |
| Candidate-library SHA-256 | `5167726cbe6bd25db79549fe12b2a3acaea3b96d8b1b72207620ee7196989a6d` |
| Available example memory DB | `tem5n28hpcplvta1024x32m4swso_110a_ssg0p81v125c.db` |

The initial SSH environment does not put DC on `PATH` or inherit its license
server variable, but the explicit binary is executable and returns its
version.  The new environment script uses the explicit path and the existing
server-local license endpoint only when the caller did not already provide one,
so the later flow does not depend on an interactive `.bashrc`.

The installed `dc_shell -version` emits the complete O-2018.06-SP1 banner but
returns status 1 without a Tcl invocation.  The preflight therefore requires
the exact banner and records that status rather than incorrectly treating this
version-query quirk as a failed installation.  A later DC-feasibility run must
still use its own explicit exit marker.

## Added read-only preflight

[`hardware/route_a/dc/check_kvzap_control_projection_dc_env.sh`](../hardware/route_a/dc/check_kvzap_control_projection_dc_env.sh)
checks the DC binary/version, candidate library, frozen archive SHA-256, top
module names, and independent exact HDL filelists.  It does not create a run
directory or invoke a synthesis Tcl script.  The sourceable companion
[`env_kvzap_control_projection_dc.sh`](../hardware/route_a/dc/env_kvzap_control_projection_dc.sh)
has only overridable path defaults.

The check passes only if Full-KV has exactly one SV entry and Route-A has
exactly 182 entries.  It also emits `unselected` markers for clock/reset,
array/black-box treatment and external-service stubs.  Those markers are
intentional blockers for a later DC invocation, not missing HDL or a failed
environment.

On 2026-10-29 it passed on `dc-server`: both filelists/top modules matched,
the frozen HDL archive SHA-256 was
`335942f0f01c24124b1fda56c6ebbd8b3425afdb2c31220cac04ff871aa94310`, and
the target-library hash matched the table above.  No DC Tcl was sourced and no
run directory was created.

## Remaining before DC feasibility

The next batch must separately choose and freeze: (1) DC constraints,
(2) array/black-box treatment, (3) typed external-service stubs and their
cost boundary, and (4) an immutable per-top run/report layout.  It must not
merge the two filelists or infer common-cost cancellation from the shared
tool/PDK environment.

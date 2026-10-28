#!/usr/bin/env bash
# Source this file on dc-server before *checking* the paired KVZap control
# projection DC environment.  It intentionally launches neither analyze nor
# elaborate and does not select a macro, clock, constraint, or external model.

_kvzap_dc_script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export KVZAP_DC_SCRIPT_DIR="${KVZAP_DC_SCRIPT_DIR:-$_kvzap_dc_script_dir}"

# DC is not on PATH in a non-interactive SSH command on the EDA server.  Use
# the explicit installed version found by the environment audit, while allowing
# a future approved installation to override it without editing this file.
export KVZAP_DC_TOOL_ROOT="${KVZAP_DC_TOOL_ROOT:-/opt/synopsys/dc2018/O-2018.06-SP1}"
export KVZAP_DC_SHELL="${KVZAP_DC_SHELL:-$KVZAP_DC_TOOL_ROOT/bin/dc_shell}"
# Non-interactive SSH does not source the server's .bashrc, where the existing
# H3 flow obtains this server-local license endpoint.  Keep a caller-provided
# license setting intact and expose the inherited default as an overrideable
# project variable; no credential or license file is stored in this repository.
export KVZAP_DC_LICENSE_FILE="${KVZAP_DC_LICENSE_FILE:-${LM_LICENSE_FILE:-27000@ercesi413}}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE:-$KVZAP_DC_LICENSE_FILE}"

# This is the existing H3-flow TSMC28 LVT .db used only as the initial
# feasibility-library candidate.  It is not a timing target, PPA corner, or
# library-selection claim; callers may override it after an approved choice.
export KVZAP_DC_PDK_ROOT="${KVZAP_DC_PDK_ROOT:-/home/yaz80/wz_project/dc_project/pdk/TSMC28}"
export KVZAP_DC_TARGET_LIBRARY="${KVZAP_DC_TARGET_LIBRARY:-$KVZAP_DC_PDK_ROOT/tcbn28hpcplusbwp12t30p140lvtssg0p81v125c.db}"

# Generated HDL is stored outside the rsync --delete Chisel workspace.  The
# archive and the extracted compilation units have independent SHA/filelist
# checks in the paired HDL freeze.  Override both paths for another host.
export KVZAP_DC_HDL_ROOT="${KVZAP_DC_HDL_ROOT:-/home/yaz80/wz_project/chisel_projects/kvpress/artifacts/qwen3_8b_32k_s1_control_projection_v1}"
export KVZAP_DC_HDL_ARCHIVE="${KVZAP_DC_HDL_ARCHIVE:-$KVZAP_DC_HDL_ROOT/paired_control_projection_hdl_qwen3_8b_32k_s1_control_projection_v1.tar.gz}"

# This root is deliberately not created by the environment precheck.  A
# separately authorized DC-feasibility run must choose an immutable run ID.
export KVZAP_DC_RUN_ROOT="${KVZAP_DC_RUN_ROOT:-/home/yaz80/wz_project/dc_project/kvzap_control_projection/runs}"

# Approved first-round, identical feasibility constraints for both tops.  They
# are a DC control-comparison baseline only, not a target frequency or system
# I/O model.  The manifest/coverage checker rejects a silent numeric override.
export KVZAP_DC_CONSTRAINT_PROFILE="${KVZAP_DC_CONSTRAINT_PROFILE:-dc_feasibility_fair_v1}"
export KVZAP_DC_CLOCK_PERIOD_NS="${KVZAP_DC_CLOCK_PERIOD_NS:-2.0}"
export KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS="${KVZAP_DC_CLOCK_SETUP_UNCERTAINTY_NS:-0.10}"
export KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS="${KVZAP_DC_CLOCK_HOLD_UNCERTAINTY_NS:-0.02}"
export KVZAP_DC_INPUT_DELAY_NS="${KVZAP_DC_INPUT_DELAY_NS:-0.20}"
export KVZAP_DC_OUTPUT_DELAY_NS="${KVZAP_DC_OUTPUT_DELAY_NS:-0.20}"
export KVZAP_DC_INPUT_TRANSITION_NS="${KVZAP_DC_INPUT_TRANSITION_NS:-0.05}"
export KVZAP_DC_OUTPUT_LOAD_PF="${KVZAP_DC_OUTPUT_LOAD_PF:-0.005}"
export KVZAP_DC_CONSTRAINT_MANIFEST="${KVZAP_DC_CONSTRAINT_MANIFEST:-$KVZAP_DC_SCRIPT_DIR/dc_feasibility_fair_v1.json}"

#!/usr/bin/env bash
# No DC, analyze, compile, DDC reload or environment source. Python reads only.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo 'Usage: bash run_wcg1_saved_artifact_validation.sh SOURCE_RUN SOURCE_INPUTS SOURCE_ARCHIVE NEW_OUTPUT FROZEN_VALIDATOR_BUNDLE'
  exit 0
fi
[[ $# == 5 ]]
source_run=$1
source_inputs=$2
source_archive=$3
validation_out=$4
validation_bundle=$5
[[ -d "$source_run" && -d "$source_inputs" && -f "$source_archive" && ! -e "$validation_out" ]]
(cd "$validation_bundle" && sha256sum -c SHA256SUMS)
# Python creates NEW_OUTPUT only after all acceptance checks pass.
# Wrapper log/exit markers live in its distinct sibling receipt directory.
receipt_dir="${validation_out}_receipt"
[[ ! -e "$receipt_dir" ]]
mkdir -p "$receipt_dir"
exec > >(tee "$receipt_dir/launcher.log") 2>&1
trap 'status=$?; echo "KVZAP_WCG1_SAVED_VALIDATION_OUTER_EXIT=$status"; echo "$status" > "$receipt_dir/exit_status"' EXIT
python3 "$validation_bundle/check_wcg1_bank_mapping.py" "$source_run" \
  --recover-empty-area --output-dir "$validation_out" \
  --inputs "$source_inputs" --archive "$source_archive" \
  --launch-record "$validation_bundle/launch_record.json" \
  --evidence-record "$validation_bundle/evidence_record.json"
(cd "$validation_bundle" && sha256sum -c SHA256SUMS)
sha256sum "$validation_out/result.json" > "$receipt_dir/result_sha256.txt"
echo KVZAP_WCG1_SAVED_VALIDATION_RUN_PASS

#!/usr/bin/env bash
# Rebuild the pinned public CACTI toolchain used by Route-A proxy studies.
set -euo pipefail

toolchain_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
lock_path="${toolchain_root}/source_lock.json"
source_dir="${toolchain_root}/src/cacti"
binary_dir="${toolchain_root}/bin"
binary_path="${binary_dir}/cacti"
manifest_path="${toolchain_root}/toolchain_manifest.json"

if [[ ! -f "${lock_path}" ]]; then
  echo "missing tracked CACTI source lock: ${lock_path}" >&2
  exit 1
fi

readarray -t lock_values < <(python3 - "${lock_path}" <<'PY'
import json
import sys

lock = json.load(open(sys.argv[1], encoding="utf-8"))
for key in ("source_url", "source_commit"):
    value = lock.get(key)
    if not isinstance(value, str) or not value:
        raise SystemExit(f"invalid {key} in source lock")
    print(value)
PY
)
source_url="${lock_values[0]}"
source_commit="${lock_values[1]}"

mkdir -p "${toolchain_root}/src" "${binary_dir}"
if [[ ! -e "${source_dir}" ]]; then
  git clone "${source_url}" "${source_dir}"
else
  if [[ ! -d "${source_dir}/.git" ]]; then
    echo "existing CACTI source path is not a Git checkout: ${source_dir}" >&2
    exit 1
  fi
  existing_origin="$(git -C "${source_dir}" config --get remote.origin.url || true)"
  if [[ "${existing_origin}" != "${source_url}" ]]; then
    echo "existing CACTI source origin differs from tracked lock" >&2
    exit 1
  fi
  if [[ -n "$(git -C "${source_dir}" status --porcelain)" ]]; then
    echo "refusing to alter a dirty CACTI source checkout: ${source_dir}" >&2
    exit 1
  fi
fi

git -C "${source_dir}" fetch --quiet origin "${source_commit}"
git -C "${source_dir}" checkout --detach --quiet "${source_commit}"
actual_commit="$(git -C "${source_dir}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${source_commit}" ]]; then
  echo "CACTI checkout did not resolve to the locked commit" >&2
  exit 1
fi

make -C "${source_dir}" -j2
install -m 0755 "${source_dir}/cacti" "${binary_path}"

python3 - "${lock_path}" "${source_dir}" "${binary_path}" "${manifest_path}" <<'PY'
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

lock_path, source_dir, binary_path, manifest_path = map(Path, sys.argv[1:])
lock = json.loads(lock_path.read_text(encoding="utf-8"))

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

source_commit = subprocess.run(
    ["git", "-C", str(source_dir), "rev-parse", "HEAD"],
    check=True, text=True, capture_output=True,
).stdout.strip()
source_origin = subprocess.run(
    ["git", "-C", str(source_dir), "config", "--get", "remote.origin.url"],
    check=True, text=True, capture_output=True,
).stdout.strip()
if source_origin != lock["source_url"] or source_commit != lock["source_commit"]:
    raise SystemExit("CACTI provenance changed while building")
template = source_dir / "cache.cfg"
if not template.is_file() or not binary_path.is_file():
    raise SystemExit("CACTI build is missing cache.cfg or executable")
manifest = {
    "manifest_schema_version": "route-a-cacti-toolchain-manifest-1.0",
    "built_at": datetime.now(timezone.utc).isoformat(),
    "source_url": source_origin,
    "source_commit": source_commit,
    "source_dir": str(source_dir.resolve()),
    "binary_path": str(binary_path.resolve()),
    "binary_sha256": sha256(binary_path),
    "template_path": str(template.resolve()),
    "template_sha256": sha256(template),
    "build_command": lock["build_command"],
}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(f"Route-A CACTI toolchain ready: {binary_path} sha256={manifest['binary_sha256']}")
PY

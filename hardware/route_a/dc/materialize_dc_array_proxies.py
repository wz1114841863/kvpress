#!/usr/bin/env python3
"""Create a DC-only typed-array-proxy source tree from frozen generated HDL.

The functional Chisel source and functional HDL archive are never edited.  A
new output directory is populated once from the archive; only the exact named
array-boundary module bodies are replaced by same-header syn_black_box stubs.
All parent-control modules and the original per-top filelists stay present.
"""

import argparse
import hashlib
import json
import re
import tarfile
from pathlib import Path


def sha256_bytes(value):
    return hashlib.sha256(value).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def locate_module(text, module):
    start_match = re.search(r"^module\s+" + re.escape(module) + r"\b", text, re.MULTILINE)
    if start_match is None:
        raise RuntimeError("missing module " + module)
    header_end = text.find(");", start_match.end())
    if header_end < 0:
        raise RuntimeError("unterminated header for " + module)
    header_end += 2
    end_match = re.search(r"^endmodule\b", text[header_end:], re.MULTILINE)
    if end_match is None:
        raise RuntimeError("missing endmodule for " + module)
    module_end = header_end + end_match.end()
    return start_match.start(), header_end, module_end


def proxy_module(text, module):
    start, header_end, module_end = locate_module(text, module)
    header = text[start:header_end]
    proxy = "(* syn_black_box = 1 *) /* synthesis syn_black_box */\n" + header + "\nendmodule"
    return text[:start] + proxy + text[module_end:], sha256_bytes(header.encode("utf-8"))


def require_parent(text, parent):
    start, header_end, module_end = locate_module(text, parent)
    body = text[header_end:module_end]
    if "syn_black_box" in body:
        raise RuntimeError("parent unexpectedly black-boxed: " + parent)
    if not body.strip():
        raise RuntimeError("parent unexpectedly empty: " + parent)


def safe_extract(archive, output):
    root = output.resolve()
    for member in archive.getmembers():
        target = (root / member.name).resolve()
        if root not in target.parents and target != root:
            raise RuntimeError("unsafe archive member " + member.name)
    archive.extractall(str(output))


def archive_text(archive, member):
    handle = archive.extractfile(archive.getmember(member))
    if handle is None:
        raise RuntimeError("cannot read archive member " + member)
    return handle.read().decode("utf-8")


def validate_manifest_against_archive(archive, manifest):
    """Fail before extraction if a boundary or retained parent is misnamed."""
    for boundary in manifest["boundaries"]:
        text = archive_text(archive, boundary["source_member"])
        locate_module(text, boundary["module"])
        for parent in boundary["parent_controls"]:
            parent_text = archive_text(archive, parent["source_member"])
            require_parent(parent_text, parent["module"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.load(args.manifest.open("r"))
    if sha256_file(args.archive) != manifest["input_hdl_archive_sha256"]:
        raise RuntimeError("frozen HDL archive SHA-256 mismatch")
    if args.output.exists() and any(args.output.iterdir()):
        raise RuntimeError("refusing to overwrite non-empty output " + str(args.output))
    args.output.mkdir(parents=True, exist_ok=True)
    with tarfile.open(str(args.archive), "r:gz") as archive:
        validate_manifest_against_archive(archive, manifest)
        safe_extract(archive, args.output)

    report = {
        "schema_version": "kvzap-dc-array-proxy-materialization-report-v1",
        "input_hdl_archive_sha256": manifest["input_hdl_archive_sha256"],
        "proxy_manifest_sha256": sha256_file(args.manifest),
        "boundaries": [],
        "filelists": {},
        "pass": False,
    }
    for boundary in manifest["boundaries"]:
        path = args.output / boundary["source_member"]
        if not path.is_file():
            raise RuntimeError("missing extracted source " + str(path))
        original = path.read_text(encoding="utf-8")
        updated, header_sha = proxy_module(original, boundary["module"])
        path.write_text(updated, encoding="utf-8")
        proxy_start, proxy_header_end, proxy_end = locate_module(updated, boundary["module"])
        proxy_body = updated[proxy_header_end:proxy_end]
        if "syn_black_box" not in updated[max(0, proxy_start - 96):proxy_start] or proxy_body.strip() != "endmodule":
            raise RuntimeError("invalid proxy materialization for " + boundary["module"])
        for parent in boundary["parent_controls"]:
            parent_path = args.output / parent["source_member"]
            require_parent(parent_path.read_text(encoding="utf-8"), parent["module"])
        report["boundaries"].append({
            "id": boundary["id"],
            "module": boundary["module"],
            "source_member": boundary["source_member"],
            "typed_header_sha256": header_sha,
            "proxy_source_sha256": sha256_file(path),
            "retained_parent_controls": [parent["module"] for parent in boundary["parent_controls"]],
        })

    filelists = manifest.get("filelists", [
        {"top": "full_kv", "root": ".", "path": "full_kv_control_projection.f", "expected_entries": 1},
        {"top": "route_a", "root": "route_a_control_projection_split", "path": "route_a_control_projection.f", "expected_entries": 182},
    ])
    for item in filelists:
        top = item["top"]
        root = args.output / item["root"]
        filelist = item["path"]
        expected = item["expected_entries"]
        entries = [line.strip() for line in (root / filelist).read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(entries) != expected or len(entries) != len(set(entries)):
            raise RuntimeError("invalid " + top + " filelist")
        if any(not (root / entry).is_file() for entry in entries):
            raise RuntimeError("missing filelist entry for " + top)
        report["filelists"][top] = {
            "path": str((root / filelist).relative_to(args.output)),
            "entries": len(entries),
            "sha256": sha256_file(root / filelist),
        }
    report["pass"] = True
    with (args.output / "dc_array_proxy_materialization_report.json").open("w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("KVZAP_DC_ARRAY_PROXY_MATERIALIZATION_PASS output=" + str(args.output))


if __name__ == "__main__":
    main()

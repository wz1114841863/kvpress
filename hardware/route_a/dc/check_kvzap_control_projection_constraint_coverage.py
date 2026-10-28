#!/usr/bin/env python3
"""Static coverage check for the frozen paired DC constraint baseline.

The checker never invokes DC.  It parses the actual archived SV top headers,
checks the manifest, and records the coverage that the collection-based Tcl
will apply once a separately authorized DC run elaborates each top.
"""

import argparse
import hashlib
import json
import re
import tarfile


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def archive_member(archive, name):
    member = archive.getmember(name)
    handle = archive.extractfile(member)
    if handle is None:
        raise RuntimeError("cannot extract " + name)
    return handle.read().decode("utf-8")


def parse_top_ports(text, top):
    match = re.search(r"^module\s+" + re.escape(top) + r"\s*\(", text, re.MULTILINE)
    if not match:
        raise RuntimeError("missing module " + top)
    end = text.find(");", match.end())
    if end < 0:
        raise RuntimeError("unterminated header for " + top)
    header = text[match.end():end]
    direction = None
    ports = []
    for raw in header.split(","):
        item = re.sub(r"//.*", "", raw).strip()
        if not item:
            continue
        direction_match = re.match(r"^(input|output)\b(.*)$", item, re.DOTALL)
        if direction_match:
            direction = direction_match.group(1)
            item = direction_match.group(2).strip()
        if direction is None:
            raise RuntimeError("port direction missing near " + item)
        item = re.sub(r"\[[^\]]+\]", "", item).strip()
        name_match = re.search(r"([A-Za-z_][A-Za-z0-9_$]*)\s*$", item)
        if not name_match:
            raise RuntimeError("cannot parse port declaration " + item)
        ports.append((direction, name_match.group(1)))
    return ports


def validate_filelist(archive, root, filelist, expected_count):
    entries = [line.strip() for line in archive_member(archive, filelist).splitlines() if line.strip()]
    if len(entries) != expected_count:
        raise RuntimeError(filelist + " has " + str(len(entries)) + " entries")
    if len(entries) != len(set(entries)):
        raise RuntimeError(filelist + " contains duplicates")
    names = set(archive.getnames())
    missing = [root + entry for entry in entries if root + entry not in names]
    if missing:
        raise RuntimeError(filelist + " refers to missing member " + missing[0])
    return {"member": filelist, "sha256": sha256_bytes(archive_member(archive, filelist).encode("utf-8")), "entries": len(entries)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--archive", required=True)
    parser.add_argument("--constraints", required=True)
    parser.add_argument("--library", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    manifest = json.load(open(args.manifest, "r"))
    if manifest["profile_id"] != "dc_feasibility_fair_v1":
        raise RuntimeError("unexpected profile id")
    expected = manifest["integrity"]
    if sha256_file(args.archive) != expected["hdl_archive_sha256"]:
        raise RuntimeError("HDL archive SHA-256 mismatch")
    if sha256_file(args.constraints) != expected["constraint_tcl_sha256"]:
        raise RuntimeError("constraint Tcl SHA-256 mismatch")
    if sha256_file(args.library) != expected["target_library_sha256"]:
        raise RuntimeError("target library SHA-256 mismatch")

    constraint_text = open(args.constraints, "r").read()
    forbidden = ["set_false_path", "set_multicycle_path"]
    found_forbidden = [token for token in forbidden if token in constraint_text]
    if found_forbidden:
        raise RuntimeError("forbidden path-exception command: " + ", ".join(found_forbidden))
    required_tcl = ["create_clock", "set_clock_uncertainty -setup", "set_clock_uncertainty -hold", "set_input_delay", "set_output_delay", "set_input_transition", "set_load"]
    missing_tcl = [token for token in required_tcl if token not in constraint_text]
    if missing_tcl:
        raise RuntimeError("missing constraint command: " + ", ".join(missing_tcl))

    report = {
        "schema_version": "kvzap-dc-constraint-coverage-v1",
        "profile_id": manifest["profile_id"],
        "static_only": True,
        "tool_ignored_constraints": ["deferred_until_DC_check_timing_and_report_constraint"],
        "path_exceptions_present": found_forbidden,
        "tops": {},
    }
    with tarfile.open(args.archive, "r:gz") as archive:
        for top_id, definition in manifest["tops"].items():
            filelist = validate_filelist(archive, definition["filelist_root"], definition["filelist"], definition["expected_file_count"])
            text = archive_member(archive, definition["top_sv"])
            ports = parse_top_ports(text, definition["top_module"])
            clocks = [name for direction, name in ports if name == "clock"]
            resets = [name for direction, name in ports if name == "reset"]
            inputs = [name for direction, name in ports if direction == "input"]
            outputs = [name for direction, name in ports if direction == "output"]
            if clocks != ["clock"] or resets != ["reset"]:
                raise RuntimeError(top_id + " has unexpected clock/reset port classification")
            timed_inputs = [name for name in inputs if name != "clock"]
            report["tops"][top_id] = {
                "top_module": definition["top_module"],
                "filelist": filelist,
                "port_counts": {"clock": 1, "synchronous_reset": 1, "ordinary_inputs": len(timed_inputs), "outputs": len(outputs)},
                "clock_excluded_from_input_delay": ["clock"],
                "reset_timed_as_ordinary_input": ["reset"],
                "unconstrained_inputs": [],
                "unconstrained_outputs": [],
                "coverage": "all_inputs_except_clock_and_all_outputs_by_collection",
            }
    report["pass"] = True
    with open(args.output, "w") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)
        handle.write("\n")


if __name__ == "__main__":
    main()

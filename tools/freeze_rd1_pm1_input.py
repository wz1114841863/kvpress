#!/usr/bin/env python3
"""Compose frozen RD1 RTL with the accepted, same-header PM1 contextual child."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import tarfile


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def header(path):
    lines = []
    with path.open() as f:
        for line in f:
            if lines or line.startswith("module "):
                lines.append(line)
                if ");" in line:
                    break
    text = "".join(lines)
    return re.sub(r"\s+", "", text[text.index("(") + 1:text.index(");")])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("pm1_child", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    assert not args.output.exists()
    archive = Path(str(args.baseline) + ".tar.gz")
    assert sha(archive) == "9494f1dc4b47f1bfbcffe655b75e20a0d4c9cd75fb9802b5d454f870ae02dc5b"
    expected_files = set((args.baseline / "route_a_control_projection_successor.f").read_text().splitlines())
    expected_files.update(("full_kv_control_projection.sv", "full_kv_control_projection.f", "route_a_control_projection_successor.f"))
    verified = set()
    with tarfile.open(archive, "r|gz") as tar:
        for member in tar:
            if member.name not in expected_files:
                continue
            h = hashlib.sha256()
            with tar.extractfile(member) as stream:
                for block in iter(lambda: stream.read(1048576), b""):
                    h.update(block)
            assert sha(args.baseline / member.name) == h.hexdigest(), member.name
            verified.add(member.name)
    assert verified == expected_files, "baseline raw files disagree with immutable archive"
    assert sha(args.pm1_child) == "dfaf40814b0372962b1720c7c9289271d6dc60158fc0d2b09238e3bbe0496671"
    assert sha(args.baseline / "full_kv_control_projection.sv") == "5e4d9918030e3d517d9913ff7c56e2325bd3c1f640e1a844d88a8a4473792256"
    old_child = args.baseline / "route_a_control_projection_split/route_a_page_manager.sv"
    assert sha(old_child) == "f5e3299f9af08b05ac1de3c2a09967303fa2294f4c31dc2b81f7dccb3bde97b4"
    assert header(old_child) == header(args.pm1_child), "PM1 contextual port mismatch"
    shutil.copytree(args.baseline, args.output)
    new_child = args.output / "route_a_control_projection_split/route_a_page_manager.sv"
    changed = 0
    with args.pm1_child.open() as src, new_child.open("w") as dst:
        for line in src:
            if re.match(r"^module route_a_page_manager_pm1\b", line):
                line = line.replace("module route_a_page_manager_pm1", "module route_a_page_manager", 1)
                changed += 1
            dst.write(line)
    assert changed == 1 and header(new_child) == header(old_child)
    entries = (args.output / "route_a_control_projection_successor.f").read_text().splitlines()
    assert len(entries) == len(set(entries)) == 48
    differences = [name for name in entries if sha(args.output / name) != sha(args.baseline / name)]
    assert differences == ["route_a_control_projection_split/route_a_page_manager.sv"]
    assert all(sha(args.output / name) == sha(args.baseline / name) for name in ("full_kv_control_projection.sv", "full_kv_control_projection.f", "route_a_control_projection_successor.f"))
    record = dict(schema="rd1-pm1-composed-input-1", composition="accepted RD1 raw HDL plus accepted PM1 contextual child; module declaration name only normalized", changed_compilation_units=differences, unchanged_route_units=47, full_kv="byte_identical", rd2=False, wcg1=False, baseline=str(args.baseline), pm1_child=str(args.pm1_child), pm1_child_sha256=sha(args.pm1_child), normalized_child_sha256=sha(new_child), route_files_sha256={name: sha(args.output / name) for name in entries})
    (args.output / "composition.json").write_text(json.dumps(record, indent=2) + "\n")
    print("KVZAP_RD1_PM1_COMPOSITION_PASS unchanged=47 changed=1 ports=identical")


if __name__ == "__main__":
    main()

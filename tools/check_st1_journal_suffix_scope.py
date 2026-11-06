#!/usr/bin/env python3
"""Replay pinned Chisel predicates for ST1 scope; not HDL simulation/equivalence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "hardware/route_a/chisel/src/main/scala/kvpress/routea/incremental/RouteAIncrementalSkeletons.scala"
FIELDS = ("transaction_identity", "payload_handle_or_address", "source_generation", "destination_endpoint")


class UInt(int):
    def __call__(self, high: int, low: int) -> UInt:
        return UInt((int(self) >> low) & ((1 << (high - low + 1)) - 1))


def record(**kwargs):
    return NS(**{k: UInt(v) if isinstance(v, int) else v for k, v in kwargs.items()})


def identity(value):
    return record(request_id=value >> 2, incarnation=value & 3, asUInt=value)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assignment(source, prefix):
    prefix = prefix.rstrip()
    lines = source.splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith("  " + prefix)]
    if len(matches) != 1:
        raise ValueError(f"expected unique assignment: {prefix}")
    i = matches[0]
    expression = [lines[i][len("  " + prefix):].strip()]
    for line in lines[i + 1:]:
        if not line.strip() or not line.startswith("    "):
            break
        expression.append(line.strip())
    return " ".join(expression)


class Predicates:
    def __init__(self, source):
        wrapper = source.split("final class RouteAM2P3Wrapper", 1)[1].split(
            "final class RouteAR5AvailabilityArrayBoundary", 1
        )[0]
        names = (
            "admissionCoordinate", "admissionOrdinalMask", "admissionAuthorityMatches",
            "pendingPayloadBindingMatches", "admissionStageMatches", "pendingBindingOffered",
            "admissionJoinReady", "packReadOrdinal", "packReadOrdinalMask",
            "packReadMemberPresent", "packReadBindingPresent", "packReadStageLive", "packReadLegal",
        )
        self.original = {name: assignment(wrapper, f"val {name} = ") for name in names}
        for name in ("admission_context_in.ready", "admission_authority_in.ready",
                     "pending_payload_binding_in.ready", "p3_pack_read_work_in.ready",
                     "p3_pack_read_issue_out.valid"):
            self.original[name] = assignment(wrapper, f"io.{name} := ")
        match = re.search(r"assert\((!reconciliationPresent\(admission\.group_member_ordinal\(5, 0\)\))\)", wrapper)
        if not match:
            raise ValueError("missing original duplicate-journal assertion")
        self.original["journal_assertion"] = match.group(1)
        assert "reconciliation" not in self.original["admissionJoinReady"]
        assert "member_ordinal <" in self.original["packReadLegal"]
        assert wrapper.count("membershipPayloadBindings(") == 3
        self.compiled = {}
        allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
                   ast.BinOp, ast.Add, ast.Mult, ast.Sub, ast.LShift, ast.BitAnd,
                   ast.BitOr, ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
                   ast.Gt, ast.GtE, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Attribute)
        for name, original in self.original.items():
            expr = re.sub(r"(\d+)\.U\([^)]*\)", r"\1", original)
            expr = re.sub(r"\.U\b", "", expr)
            expr = expr.replace("=/=", "!=").replace("===", "==")
            expr = expr.replace("&&", " and ").replace("||", " or ")
            expr = re.sub(r"!(?!=)", " not ", expr).strip()
            tree = ast.parse(expr, mode="eval")
            if any(not isinstance(node, allowed) for node in ast.walk(tree)):
                raise ValueError(f"unsupported expression: {name}: {original}")
            self.compiled[name] = compile(tree, f"<source-predicate:{name}>", "eval")

    def get(self, name, env):
        return eval(self.compiled[name], {"__builtins__": {}}, env)


class Fixture:
    """Explicit state fixtures; no claim of executing the full wrapper FSM."""

    def __init__(self, predicates):
        self.p = predicates
        self.state = [1] * 36  # Preclaimed RESERVED fixtures, not an RTL claim trace.
        self.count = [64] * 36
        self.generation = [1] * 36
        self.member_present = [0] * 36
        self.binding_present = [0] * 36
        self.refs = [[0] * 64 for _ in range(36)]
        self.suffix = [[None] * 64 for _ in range(36)]
        self.journal = [None] * 64

    def env(self):
        return dict(
            initialized=True, observationActive=lambda b: False,
            stageState=lambda b: self.state[b], stageHead=lambda b: b % 8,
            stageTag=lambda b: b + 1, stageValidRecords=lambda b: self.count[b],
            stageGeneration=lambda b: self.generation[b],
            membershipPresent=lambda b: self.member_present[b],
            membershipPayloadBindingPresent=lambda b: self.binding_present[b],
            reconciliationPresent=lambda o: self.journal[o] is not None,
            RouteAAuthorityStateCode=NS(Hot=1, Pending=2),
            StateReserved=1, StateFilling=2, StateComplete=3, StateWriteIssued=4, StateDurable=5,
        )

    def binding(self, bank, ordinal, value=0):
        return record(
            layer=bank, kv_head=bank % 8, logical_position=ordinal + 128,
            entry_id=(ordinal + 128) * 288 + bank * 8 + bank % 8,
            payload_ref=(1 << 63) | (bank << 16) | ordinal,
            transaction_group_tag=bank + 1, group_member_ordinal=ordinal,
            group_valid_records=self.count[bank], transaction_identity=identity(value & 31),
            payload_handle_or_address=value & ((1 << 64) - 1),
            source_generation=(value >> 64) & 255, destination_endpoint=(value >> 72) & 7,
        )

    def admission(self, binding, offered=True, valid=True, authority_valid=True, commit=True):
        env = self.env()
        io = NS(
            pending_payload_binding_in=NS(valid=offered),
            admission_context_in=NS(valid=valid), admission_authority_in=NS(valid=authority_valid),
        )
        env.update(admission=binding, admissionLayer=binding.layer, pendingPayloadBinding=binding,
                   admissionAuthority=record(entry_id=binding.entry_id, from_authority=1,
                                             to_authority=2, transaction_group_tag=binding.transaction_group_tag), io=io)
        for name in ("admissionCoordinate", "admissionOrdinalMask", "admissionAuthorityMatches",
                     "pendingPayloadBindingMatches", "admissionStageMatches", "pendingBindingOffered", "admissionJoinReady"):
            env[name] = self.p.get(name, env)
        ready = bool(self.p.get("admission_context_in.ready", env))
        fire = valid and ready
        assertion = not (fire and offered) or bool(self.p.get("journal_assertion", env))
        if fire and commit and assertion:
            b, o = binding.layer, binding.group_member_ordinal
            self.member_present[b] |= 1 << o
            self.refs[b][o] = binding.payload_ref
            if offered:
                self.binding_present[b] |= 1 << o
                self.suffix[b][o] = binding
                self.journal[o] = binding
        return ready, fire, assertion

    def checked(self, work, use_journal=False, valid=True, sink_ready=True):
        b, o = work.layer, work.member_ordinal(5, 0)
        if b >= 36:
            raise ValueError("out-of-range bank is unspecified; not replayed as a pass")
        binding = self.journal[o] if use_journal else self.suffix[b][o]
        # Invalid data are arbitrary here; ready must be masked by real presence.
        binding = binding or self.binding(b, o, 0)
        env = self.env()
        env.update(packReadWork=work, packReadLayer=b, packReadBinding=binding,
                   packReadMember=record(payload_ref=self.refs[b][o]),
                   io=NS(p3_pack_read_work_in=NS(valid=valid), p3_pack_read_issue_out=NS(ready=sink_ready)))
        for name in ("packReadOrdinal", "packReadOrdinalMask", "packReadMemberPresent",
                     "packReadBindingPresent", "packReadStageLive", "packReadLegal"):
            env[name] = self.p.get(name, env)
        return (bool(self.p.get("p3_pack_read_work_in.ready", env)),
                bool(self.p.get("p3_pack_read_issue_out.valid", env)))

    @staticmethod
    def work(binding, **changes):
        values = vars(binding).copy()
        values["member_ordinal"] = binding.group_member_ordinal
        values["stage_generation"] = 1
        values.update(changes)
        return record(**values)

    def compare(self, work, **kwargs):
        old = self.checked(work, **kwargs)
        new = self.checked(work, use_journal=True, **kwargs)
        assert old == new, (old, new, work)
        return old


def replay(predicates):
    results = []

    def done(name, checks, **extra):
        results.append(dict(name=name, evidence="SOURCE_PREDICATE_REPLAY", status="PASS", checks=checks, **extra))

    # All bank/ordinal addresses, one independent reset epoch per bank.
    count = 0
    for bank in range(36):
        f = Fixture(predicates)
        for ordinal in range(64):
            binding = f.binding(bank, ordinal, (7 << 72) | (255 << 64) | (1 << 63) | ordinal)
            work = f.work(binding)
            assert f.compare(work) == (False, False)  # pre-edge presence
            assert f.admission(binding) == (True, True, True)
            for valid in (False, True):
                for sink in (False, True):
                    assert f.compare(work, valid=valid, sink_ready=sink) == (sink, valid)
                    count += 1
            assert all(getattr(f.suffix[bank][ordinal], x) == getattr(f.journal[ordinal], x) for x in FIELDS)
    done("full_36x64_addresses_preedge_and_valid_low", count)

    f = Fixture(predicates)
    a, b = f.binding(2, 0, 1 << 63), f.binding(35, 63, (3 << 72) | (5 << 64) | 17)
    assert f.admission(a)[1] and f.admission(b)[1]
    for _ in range(5):
        assert f.compare(f.work(a), valid=False) == (True, False)
        assert f.compare(f.work(b), sink_ready=False) == (False, True)
    done("independent_crossbank_reads_and_stalls", 10)
    c = f.binding(2, 1, 85)
    assert f.admission(c)[1]
    assert f.compare(f.work(a))[0] and f.compare(f.work(c))[0]
    done("independent_samebank_different_ordinal_reads", 2)

    checked = 0
    for field, width in (("payload_handle_or_address", 64), ("source_generation", 8), ("destination_endpoint", 3)):
        for bit in range(width):
            bad = f.work(a, **{field: UInt(getattr(a, field) ^ (1 << bit))})
            assert f.compare(bad, valid=False) == (False, False)
            checked += 1
    for bit in range(5):
        assert f.compare(f.work(a, transaction_identity=identity(a.transaction_identity.asUInt ^ (1 << bit)))) == (False, False)
        checked += 1
    done("all_80_suffix_bits_independent_mismatch_rejection", checked)
    for bit in range(64):
        assert f.compare(f.work(a, payload_ref=UInt(a.payload_ref ^ (1 << bit))), valid=False) == (False, False)
    assert f.compare(f.work(a, stage_generation=UInt(2)), valid=False) == (False, False)
    done("payload_reference_and_stale_stage_rejection", 65)

    for ordinal in range(128):
        ready, out_valid = f.compare(f.work(a, member_ordinal=UInt(ordinal)), valid=False)
        if ordinal >= 64:
            assert not ready and not out_valid
    done("full_seven_bit_checked_ordinal", 128)

    for population in (1, 2, 63, 64):
        tail = Fixture(predicates)
        tail.count[35] = population
        binding = tail.binding(35, population - 1, 1 << 63)
        assert tail.admission(binding) == (True, True, True)
        assert tail.compare(tail.work(binding), valid=False) == (True, False)
        assert tail.compare(tail.work(binding, member_ordinal=UInt(population)), valid=False) == (False, False)
    done("tail_population_1_2_63_64_full_width_guard", 8)

    atomic = Fixture(predicates)
    binding = atomic.binding(0, 0, 3)
    assert atomic.admission(binding, authority_valid=False, commit=False)[1] is False
    assert atomic.admission(binding, valid=False, commit=False)[1] is False
    assert not any(atomic.member_present) and not any(atomic.journal)
    done("missing_context_or_authority_no_accepted_write", 2)

    unbound = Fixture(predicates)
    for bank in range(36):
        for ordinal in range(64):
            binding = unbound.binding(bank, ordinal)
            assert unbound.admission(binding, offered=False) == (True, True, True)
            assert unbound.compare(unbound.work(binding), valid=False) == (False, False)
    assert sum(v.bit_count() for v in unbound.member_present) == 2304
    assert not any(unbound.binding_present) and not any(unbound.journal)
    done("all_2304_unbound_member_slots_preserved", 2304)

    # A journal binding at the same ordinal must not grant another bank a binding.
    assert f.compare(f.work(f.binding(3, 0)), valid=False) == (False, False)
    unbound_binding = f.binding(3, 0)
    assert f.admission(unbound_binding, offered=False)[1]
    assert f.compare(f.work(unbound_binding), valid=False) == (False, False)
    done("other_bank_absent_and_unbound_rejection", 2)

    fresh = Fixture(predicates)
    original = fresh.binding(0, 0, 17)
    assert fresh.admission(original) == (True, True, True)
    assert fresh.admission(original, commit=False) == (False, False, True)
    done("same_bank_duplicate_rejected_by_actual_ready", 1)
    alias = fresh.binding(1, 0, 34)
    # Stop the accepted prefix at the real assertion failure; do not commit it.
    ready, fire, assertion_ok = fresh.admission(alias, commit=False)
    assert ready and fire and not assertion_ok
    done("crossbank_duplicate_original_assertion_detected", 1,
         accepted_prefix=True, assertion_result=False, legal_suffix_trace=False)
    # Separately inspect the counterfactual overwrite equation. Not a legal run.
    fresh.journal[0] = alias
    work = fresh.work(original)
    before = fresh.checked(work, valid=False)
    after = fresh.checked(work, use_journal=True, valid=False)
    assert before == (True, False) and after == (False, False)
    results.append(dict(name="post_assertion_alias_diagnostic", evidence="COUNTERFACTUAL_ONLY",
                        status="EXPECTED_DIVERGENCE", original=before, naive_shared=after,
                        counted_as_legal_equivalence=False))

    f.binding_present[2] = 0  # Claim/reset mask equation; not full claim FSM.
    assert f.compare(f.work(a)) == (False, False)
    done("claim_mask_clear_with_journal_retained", 1)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="new result directory; never overwritten")
    args = parser.parse_args()
    if not __debug__:
        raise RuntimeError("run without -O: audit assertions must remain enabled")
    if args.output_dir.exists():
        raise FileExistsError(f"immutable result directory exists: {args.output_dir}")
    authority = ROOT / "analysis/dc_compact_store_p0_evidence_20261106.json"
    pins = json.loads(authority.read_text())["sha256"]
    for name, expected in pins.items():
        if digest(ROOT / name) != expected:
            raise ValueError(f"source/evidence drift: {name}")
    source = (ROOT / SOURCE).read_text()
    predicates = Predicates(source)
    results = replay(predicates)
    report = dict(
        schema_version="route-a-st1-scope-key-check-1",
        source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        checker_sha256=digest(Path(__file__)),
        evidence_class="source_predicate_replay_not_hdl_simulation_or_rtl_equivalence",
        source_sha256=pins, expressions=predicates.original, cases=results,
        generic_replacement_disposition="NOT_ELIGIBLE_WITHOUT_NEW_SCOPE_AUTHORITY",
        production_conditional_candidate="retained_not_implemented",
        rtl_modified=False, remote_access=False, synthesis_run=False,
    )
    args.output_dir.mkdir(parents=True, exist_ok=False)
    output = args.output_dir / "report.json"
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"ST1_SOURCE_PREDICATE_CHECK_PASS cases={len(results)} expected_alias_divergence=1")
    print(f"report={output} sha256={digest(output)}")
    print("GENERIC_JOURNAL_ONLY_REPLACEMENT_NOT_ELIGIBLE; no HDL equivalence or mapped result")


if __name__ == "__main__":
    main()

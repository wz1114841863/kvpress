"""Check that the ST1 audit detects changes to the predicates it is auditing."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("st1_scope", ROOT / "tools/check_st1_journal_suffix_scope.py")
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)
SOURCE = (ROOT / AUDIT.SOURCE).read_text()


def test_assignment_extractor_handles_multiline_rhs_without_trailing_space():
    assert AUDIT.assignment("  val field =\n    left &&\n    right\n  val next = 0\n", "val field = ") == " left && right"


def test_audit_detects_incorrect_valid_gating_of_continuous_ready():
    before = "io.p3_pack_read_work_in.ready := packReadLegal && io.p3_pack_read_issue_out.ready"
    after = "io.p3_pack_read_work_in.ready := io.p3_pack_read_work_in.valid && packReadLegal && io.p3_pack_read_issue_out.ready"
    assert SOURCE.count(before) == 1
    with pytest.raises(AssertionError):
        AUDIT.replay(AUDIT.Predicates(SOURCE.replace(before, after)))


def test_audit_rejects_new_admission_gate_using_journal_presence():
    before = "val admissionJoinReady = admissionStageMatches && admissionAuthorityMatches &&"
    after = before + " !reconciliationPresent(admission.group_member_ordinal(5, 0)) &&"
    assert SOURCE.count(before) == 1
    with pytest.raises(AssertionError):
        AUDIT.Predicates(SOURCE.replace(before, after))


def test_audit_rejects_replacing_full_ordinal_guard_with_truncated_ordinal():
    before = "packReadWork.member_ordinal < stageValidRecords(packReadLayer)"
    after = "packReadOrdinal < stageValidRecords(packReadLayer)"
    assert SOURCE.count(before) == 1
    with pytest.raises(AssertionError):
        AUDIT.Predicates(SOURCE.replace(before, after))

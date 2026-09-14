from types import SimpleNamespace

from kvpress.presses.kvzap_press import KVzapModel, KVzapPress


def test_default_predictor_resolution_is_unchanged(monkeypatch):
    calls = []

    def fake_load(cls, name, revision=None):
        calls.append((name, revision))
        return object()

    monkeypatch.setattr(KVzapModel, "from_pretrained", classmethod(fake_load))
    press = KVzapPress(model_type="linear", predictor_revision="rev")
    press.post_init_from_model(SimpleNamespace(config=SimpleNamespace(name_or_path="NousResearch/Meta-Llama-3.1-8B-Instruct")))
    assert calls == [("nvidia/KVzap-linear-Meta-Llama-3.1-8B-Instruct", "rev")]
    assert press.kvzap_model_name == calls[0][0]


def test_explicit_predictor_override_replaces_only_repository_id(monkeypatch):
    calls = []

    def fake_load(cls, name, revision=None):
        calls.append((name, revision))
        return object()

    monkeypatch.setattr(KVzapModel, "from_pretrained", classmethod(fake_load))
    official = "nvidia/KVzap-linear-Llama-3.1-8B-Instruct"
    press = KVzapPress(model_type="linear", predictor_revision="rev", predictor_repo_id_override=official)
    press.post_init_from_model(SimpleNamespace(config=SimpleNamespace(name_or_path="NousResearch/Meta-Llama-3.1-8B-Instruct")))
    assert calls == [(official, "rev")]
    assert press.kvzap_model_name == official

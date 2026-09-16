import pytest

from tools.run_kvzap_route_a40_policy_gate import cuda_environment


def test_cuda_environment_records_single_visible_device(monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "3")
    monkeypatch.setattr("torch.cuda.is_available", lambda: True)
    monkeypatch.setattr("torch.cuda.device_count", lambda: 1)
    monkeypatch.setattr("torch.cuda.get_device_name", lambda index: "test-gpu")
    assert cuda_environment(require_single_visible_device=True) == {
        "cuda_available": True,
        "visible_cuda_device_count": 1,
        "cuda_visible_devices": "3",
        "visible_device_names": ["test-gpu"],
    }


def test_cuda_environment_rejects_multi_device_auto_dispatch(monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    monkeypatch.setattr("torch.cuda.is_available", lambda: True)
    monkeypatch.setattr("torch.cuda.device_count", lambda: 8)
    monkeypatch.setattr("torch.cuda.get_device_name", lambda index: f"gpu-{index}")
    with pytest.raises(RuntimeError, match="exactly one visible CUDA device"):
        cuda_environment(require_single_visible_device=True)

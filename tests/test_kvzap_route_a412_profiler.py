from tools.run_kvzap_route_a412_profiler import operator_rows


class Event:
    def __init__(self, key, count, cuda, cpu):
        self.key = key
        self.count = count
        self.device_time_total = cuda
        self.cpu_time_total = cpu
        self.self_device_time_total = cuda / 2
        self.self_cpu_time_total = cpu / 2
        self.self_cpu_memory_usage = 1
        self.cpu_memory_usage = 2
        self.self_device_memory_usage = 3
        self.device_memory_usage = 4


def test_operator_rows_normalizes_and_sorts_by_device_then_cpu_time():
    rows = operator_rows([Event("cpu_heavy", 2, 1.0, 30.0), Event("cuda_heavy", 3, 20.0, 2.0)], top_operators=1)
    assert rows == [{"operator": "cuda_heavy", "count": 3, "self_cpu_time_total_us": 1.0, "cpu_time_total_us": 2.0, "self_device_time_total_us": 10.0, "device_time_total_us": 20.0, "self_cpu_memory_usage_bytes": 1.0, "cpu_memory_usage_bytes": 2.0, "self_device_memory_usage_bytes": 3.0, "device_memory_usage_bytes": 4.0}]


def test_operator_rows_falls_back_to_legacy_cuda_field_names():
    event = Event("legacy", 1, 0.0, 1.0)
    del event.device_time_total
    del event.self_device_time_total
    del event.device_memory_usage
    del event.self_device_memory_usage
    event.cuda_time_total = 9.0
    event.self_cuda_time_total = 4.0
    event.cuda_memory_usage = 8
    event.self_cuda_memory_usage = 7
    assert operator_rows([event], top_operators=1)[0]["device_time_total_us"] == 9.0

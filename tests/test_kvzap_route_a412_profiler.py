from tools.run_kvzap_route_a412_profiler import operator_rows


class Event:
    def __init__(self, key, count, cuda, cpu):
        self.key = key
        self.count = count
        self.cuda_time_total = cuda
        self.cpu_time_total = cpu
        self.self_cuda_time_total = cuda / 2
        self.self_cpu_time_total = cpu / 2
        self.self_cpu_memory_usage = 1
        self.cpu_memory_usage = 2
        self.self_cuda_memory_usage = 3
        self.cuda_memory_usage = 4


def test_operator_rows_normalizes_and_sorts_by_cuda_then_cpu_time():
    rows = operator_rows([Event("cpu_heavy", 2, 1.0, 30.0), Event("cuda_heavy", 3, 20.0, 2.0)], top_operators=1)
    assert rows == [{"operator": "cuda_heavy", "count": 3, "self_cpu_time_total_us": 1.0, "cpu_time_total_us": 2.0, "self_cuda_time_total_us": 10.0, "cuda_time_total_us": 20.0, "self_cpu_memory_usage_bytes": 1.0, "cpu_memory_usage_bytes": 2.0, "self_cuda_memory_usage_bytes": 3.0, "cuda_memory_usage_bytes": 4.0}]

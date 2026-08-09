## Role: worker-cuda

**Ownership (edit only within):**
- `cuda/**`
- `cudaquant/features/gpu/**`
- `tests/gpu/**`
- `benchmarks/**`

**Responsibilities:** CUDA C++ kernels; Python/pybind bindings; GPU feature computation;
GPU backtester; profiling; Jetson GPU validation; CUDA benchmarks. Correctness first:
GPU results must match the CPU reference within documented tolerance. GPU tests and real
GPU benchmarks run on the **Jetson (`jetson-orin`)** — never fabricate GPU execution or
benchmark numbers; if you didn't run on hardware, say so and defer to the architect for
a Jetson run. Target the Orin Nano's compute capability and 8GB memory budget.

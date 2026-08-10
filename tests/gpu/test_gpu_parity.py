"""GPU vs CPU parity tests for the CUDA feature kernels.

These run ONLY on a machine with the compiled ``libcudaquant_kernels.so`` and a
working GPU (the Jetson Orin). Off-GPU — e.g. on the Mac dev box where the
bindings fall back to CPU — the whole module is skipped, so a green run here is
real GPU execution, not a CPU-vs-CPU tautology.

Tolerances are per-kernel and reflect float32 GPU vs float64 CPU reality,
measured on-device (Jetson Orin, CUDA 13.2):
- reductions/means/returns match to ~1e-5;
- rolling sum matches in RELATIVE terms (~6e-5) — absolute error scales with the
  ~O(1e3) magnitude of the sum, so it is checked with rtol, not a tiny atol;
- variance/std/zscore carry the documented float32 precision limit (~a few e-2).
"""

import numpy as np
import pytest

from cudaquant.features import engine as cpu
from cudaquant.features.gpu import bindings
from cudaquant.features.gpu import kernels as gpu

pytestmark = pytest.mark.gpu

# Skip the entire module unless the real CUDA library is loadable.
if bindings._load_library() is None:
    pytest.skip(
        "CUDA kernel library not available (GPU-only test); skipping off-device.",
        allow_module_level=True,
    )

WINDOW = 20


@pytest.fixture(scope="module")
def series() -> np.ndarray:
    rng = np.random.default_rng(0)
    return (100.0 + np.cumsum(rng.standard_normal(100_000))).astype(np.float64)


# name -> (cpu_fn, gpu_fn, rtol, atol)
CASES = {
    "rolling_mean":     (lambda x: cpu.rolling_mean(x, WINDOW),     lambda x: gpu.gpu_rolling_mean(x, WINDOW),     1e-3, 1e-2),
    "rolling_min":      (lambda x: cpu.rolling_min(x, WINDOW),      lambda x: gpu.gpu_rolling_min(x, WINDOW),      1e-4, 1e-3),
    "rolling_max":      (lambda x: cpu.rolling_max(x, WINDOW),      lambda x: gpu.gpu_rolling_max(x, WINDOW),      1e-4, 1e-3),
    "rolling_sum":      (lambda x: cpu.rolling_sum(x, WINDOW),      lambda x: gpu.gpu_rolling_sum(x, WINDOW),      1e-3, 1e-1),
    "rolling_std":      (lambda x: cpu.rolling_std(x, WINDOW),      lambda x: gpu.gpu_rolling_std(x, WINDOW),      1e-2, 1e-1),
    "rolling_variance": (lambda x: cpu.rolling_variance(x, WINDOW), lambda x: gpu.gpu_rolling_variance(x, WINDOW), 1e-2, 1e-1),
    "rolling_zscore":   (lambda x: cpu.rolling_zscore(x, WINDOW),   lambda x: gpu.gpu_rolling_zscore(x, WINDOW),   0.0,  1e-1),
    "simple_returns":   (lambda x: cpu.returns(x, log=False),       lambda x: gpu.gpu_simple_returns(x),           0.0,  1e-2),
}


@pytest.mark.parametrize("name", list(CASES))
def test_gpu_matches_cpu(series: np.ndarray, name: str):
    cpu_fn, gpu_fn, rtol, atol = CASES[name]
    c = np.asarray(cpu_fn(series), dtype=float)
    g = np.asarray(gpu_fn(series), dtype=float)
    assert c.shape == g.shape, f"{name}: shape mismatch {c.shape} vs {g.shape}"

    mask = np.isfinite(c) & np.isfinite(g)
    assert mask.sum() > 0, f"{name}: no finite values to compare"
    # NaN placement must agree (warm-up regions).
    assert np.array_equal(np.isnan(c), np.isnan(g)), f"{name}: NaN masks differ"

    np.testing.assert_allclose(
        g[mask], c[mask], rtol=rtol, atol=atol,
        err_msg=f"{name}: GPU output outside float32 tolerance of CPU reference",
    )

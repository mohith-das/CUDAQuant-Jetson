"""GPU vs CPU ML parity test — logistic regression.
Run on Jetson with: LD_LIBRARY_PATH=$PWD/cuda/lib:/usr/local/cuda/lib64 .venv/bin/python benchmarks/ml_gpu_parity.py
"""
import time

import numpy as np

from cudaquant.ml.gpu_models import TSLogisticRegressionGPU, get_ml_backend
from cudaquant.ml.models import TSLogisticRegression as CPULogReg

print(f"ML backend: {get_ml_backend()}")

# Generate synthetic data
rng = np.random.default_rng(42)
n_samples, n_features = 5000, 10
X = rng.normal(0, 1, (n_samples, n_features)).astype(np.float32)
true_w = rng.normal(0, 0.5, n_features).astype(np.float32)
y = ((X @ true_w + rng.normal(0, 0.1, n_samples)) > 0).astype(np.float32)

# GPU model
t0 = time.perf_counter()
gpu_model = TSLogisticRegressionGPU(lr=0.05, epochs=200, l2=0.001)
gpu_model.fit(X, y)
gpu_time = (time.perf_counter() - t0) * 1000
gpu_probs = gpu_model.predict_proba(X)
gpu_preds = gpu_model.predict(X)

# CPU model
t0 = time.perf_counter()
cpu_model = CPULogReg()
cpu_model.fit(X, y)
cpu_time = (time.perf_counter() - t0) * 1000
cpu_probs = cpu_model.predict_proba(X)
cpu_preds = cpu_model.predict(X)

# Compare
valid = ~(np.isnan(gpu_probs) | np.isnan(cpu_probs))
agreement = (gpu_preds[valid] == cpu_preds[valid]).mean()
corr = np.corrcoef(gpu_probs[valid], cpu_probs[valid])[0, 1]
gpu_acc = (gpu_preds[valid] == (y[valid] > 0)).mean()
cpu_acc = (cpu_preds[valid] == (y[valid] > 0)).mean()

print("")
print(f"Results (n={n_samples}, features={n_features}, epochs=200):")
print(f"  GPU training time:  {gpu_time:.0f} ms")
print(f"  CPU training time:  {cpu_time:.0f} ms")
print(f"  Prediction agreement: {agreement:.1%}")
print(f"  Prob correlation:    {corr:.4f}")
print(f"  GPU accuracy:        {gpu_acc:.1%}")
print(f"  CPU accuracy:        {cpu_acc:.1%}")

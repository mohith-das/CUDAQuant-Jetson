# Jetson Orin Nano Super 8GB — Environment Reference

> Auto-probed: 2026-08-09 | Commit: 6f8ba06

## Hardware
- **Device:** NVIDIA Jetson Orin Nano Super (8 GB)
- **SoC:** Tegra Orin (nvgpu)
- **Architecture:** aarch64
- **RAM:** 7.3 GiB (no swap)
- **Storage:** 233 GB NVMe (90 GB used, 131 GB available)
- **Power mode:** 25W (nvpmodel mode 1)

## OS & Kernel
- **OS:** Ubuntu 24.04 (Noble Numbat)
- **Kernel:** 6.8.12-1021-tegra (PREEMPT, aarch64)
- **Tegra release:** R39.2.0, GCID 45755727
- **Board:** generic

## JetPack / CUDA
- **JetPack:** 7.2 (build b187)
- **CUDA Toolkit:** 13.2 (V13.2.78)
- **Driver:** 595.78
- **nvcc:** `/usr/local/cuda/bin/nvcc`
- **Libraries:** libcudart 13.2.75, full CUDA 13.2 metapackage
- **Profiling:** CUPTI 13.2 available
- **Debug:** cuda-gdb 13.2 available

## Compilers
- **GCC:** 13.3.0 (Ubuntu)
- **G++:** 13.3.0 (Ubuntu)
- **CMake:** 3.28.3

## Python
- **Version:** 3.12.3 (system)
- **Key packages installed:**
  - numpy 1.26.4
  - pandas 2.1.4
  - scipy 1.11.4
- **NOT installed (required):** cupy, torch, fastapi, duckdb, pyarrow, scikit-learn

## Network
- **Hostname:** matt.local
- **SSH alias:** `jetson-orin` → `matt@matt.local`

## Notes
- No swap configured — 7.3 GiB RAM is the hard limit.
- All GPU memory is shared with system RAM (Unified Memory Architecture).
- CuPy and PyTorch will need CUDA 13.2-compatible builds (verify before installing).
- Do NOT install RAPIDS/cuDF without explicit Jetson aarch64 compatibility verification.

#!/usr/bin/env bash
# build.sh — Compile CUDA kernels for CUDAQuant-Jetson
# Target: Jetson Orin aarch64 (cross-compile not supported; run on device)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/build"
LIB_DIR="${SCRIPT_DIR}/lib"

# Detect CUDA
if [ -z "${CUDA_HOME:-}" ]; then
    if [ -d "/usr/local/cuda" ]; then
        CUDA_HOME="/usr/local/cuda"
    elif [ -d "/usr/local/cuda-13" ]; then
        CUDA_HOME="/usr/local/cuda-13"
    else
        echo "ERROR: CUDA not found. Set CUDA_HOME or install CUDA toolkit."
        exit 1
    fi
fi

export PATH="${CUDA_HOME}/bin:${PATH}"
echo "CUDA_HOME=${CUDA_HOME}"
echo "nvcc: $(which nvcc)"
nvcc --version | head -1

# Clean build
rm -rf "${BUILD_DIR}" "${LIB_DIR}"
mkdir -p "${BUILD_DIR}" "${LIB_DIR}"

# Configure
cd "${BUILD_DIR}"
cmake "${SCRIPT_DIR}" \
    -DCMAKE_CUDA_ARCHITECTURES=87 \
    -DCMAKE_BUILD_TYPE=Release

# Build
cmake --build . -- -j$(nproc 2>/dev/null || echo 4)

# Copy output
if [ -f "${BUILD_DIR}/libcudaquant_kernels.so" ]; then
    cp "${BUILD_DIR}/libcudaquant_kernels.so" "${LIB_DIR}/"
elif [ -f "${BUILD_DIR}/libcudaquant_kernels.dylib" ]; then
    cp "${BUILD_DIR}/libcudaquant_kernels.dylib" "${LIB_DIR}/"
fi

echo ""
echo "BUILD SUCCESSFUL"
echo "Library: $(ls -la "${LIB_DIR}"/libcudaquant_kernels.* 2>/dev/null || echo 'not found')"

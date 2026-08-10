// rolling.cu — CUDA kernels for rolling-window statistics
// Target: NVIDIA Jetson Orin (SM 8.7), CUDA 13.2

#include <cuda_runtime.h>
#include <math.h>
#include <float.h>

#define THREADS_PER_BLOCK 256
#define NAN_MASK 0x7FF8000000000000ULL  // IEEE 754 quiet NaN for double

// Helper: set value to NaN
__device__ double make_nan() {
    unsigned long long nan_bits = NAN_MASK;
    return *(double*)&nan_bits;
}

__device__ static float make_nanf() {
    unsigned int nan_bits = 0x7FC00000;
    return *(float*)&nan_bits;
}

// ── Rolling Sum (base kernel, others build on it) ──────────────────────────

extern "C" __global__ void rolling_sum_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    int n,
    int window)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx < window - 1) {
        output[idx] = make_nanf();
        return;
    }

    float sum = 0.0f;
    int start = idx - window + 1;
    for (int j = start; j <= idx; j++) {
        sum += input[j];
    }
    output[idx] = sum;
}

extern "C" void launch_rolling_sum(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_sum_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

// ── Rolling Mean ───────────────────────────────────────────────────────────

extern "C" __global__ void rolling_mean_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    int n,
    int window)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx < window - 1) {
        output[idx] = make_nanf();
        return;
    }

    float sum = 0.0f;
    int start = idx - window + 1;
    for (int j = start; j <= idx; j++) {
        sum += input[j];
    }
    output[idx] = sum / (float)window;
}

extern "C" void launch_rolling_mean(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_mean_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

// ── Rolling Variance (population) ──────────────────────────────────────────

extern "C" __global__ void rolling_variance_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    int n,
    int window)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx < window - 1) {
        output[idx] = make_nanf();
        return;
    }

    float sum = 0.0f;
    float sum_sq = 0.0f;
    int start = idx - window + 1;
    for (int j = start; j <= idx; j++) {
        float v = input[j];
        sum += v;
        sum_sq += v * v;
    }
    float mean = sum / (float)window;
    float variance = sum_sq / (float)window - mean * mean;
    output[idx] = fmaxf(variance, 0.0f);
}

extern "C" void launch_rolling_variance(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_variance_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

// ── Rolling Std ────────────────────────────────────────────────────────────

extern "C" __global__ void rolling_std_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    int n,
    int window)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx < window - 1) {
        output[idx] = make_nanf();
        return;
    }

    float sum = 0.0f;
    float sum_sq = 0.0f;
    int start = idx - window + 1;
    for (int j = start; j <= idx; j++) {
        float v = input[j];
        sum += v;
        sum_sq += v * v;
    }
    float mean = sum / (float)window;
    float variance = sum_sq / (float)window - mean * mean;
    output[idx] = sqrtf(fmaxf(variance, 0.0f));
}

extern "C" void launch_rolling_std(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_std_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

// ── Rolling Min ────────────────────────────────────────────────────────────

extern "C" __global__ void rolling_min_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    int n,
    int window)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx < window - 1) {
        output[idx] = make_nanf();
        return;
    }

    float min_val = FLT_MAX;
    int start = idx - window + 1;
    for (int j = start; j <= idx; j++) {
        min_val = fminf(min_val, input[j]);
    }
    output[idx] = min_val;
}

extern "C" void launch_rolling_min(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_min_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

// ── Rolling Max ────────────────────────────────────────────────────────────

extern "C" __global__ void rolling_max_kernel(
    const float* __restrict__ input,
    float* __restrict__ output,
    int n,
    int window)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx < window - 1) {
        output[idx] = make_nanf();
        return;
    }

    float max_val = -FLT_MAX;
    int start = idx - window + 1;
    for (int j = start; j <= idx; j++) {
        max_val = fmaxf(max_val, input[j]);
    }
    output[idx] = max_val;
}

extern "C" void launch_rolling_max(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_max_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

// zscore.cu — CUDA kernel for rolling z-score

#include <cuda_runtime.h>
#include <math.h>

#define THREADS_PER_BLOCK 256

__device__ static float make_nanf() {
    unsigned int nan_bits = 0x7FC00000;
    return *(float*)&nan_bits;
}

extern "C" __global__ void rolling_zscore_kernel(
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

    // Compute mean and std for this window
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
    float std = sqrtf(fmaxf(variance, 0.0f));

    if (std < 1e-10f) {
        output[idx] = 0.0f;
    } else {
        output[idx] = (input[idx] - mean) / std;
    }
}

extern "C" void launch_rolling_zscore(
    const float* d_input, float* d_output, int n, int window)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    rolling_zscore_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_input, d_output, n, window);
}

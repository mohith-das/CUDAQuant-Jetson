// returns.cu — CUDA kernels for simple and log returns

#include <cuda_runtime.h>
#include <math.h>

#define THREADS_PER_BLOCK 256

__device__ static float make_nanf() {
    unsigned int nan_bits = 0x7FC00000;
    return *(float*)&nan_bits;
}

extern "C" __global__ void simple_returns_kernel(
    const float* __restrict__ prices,
    float* __restrict__ output,
    int n)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx == 0) {
        output[0] = make_nanf();
        return;
    }

    output[idx] = (prices[idx] - prices[idx - 1]) / prices[idx - 1];
}

extern "C" void launch_simple_returns(
    const float* d_prices, float* d_output, int n)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    simple_returns_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_prices, d_output, n);
}

extern "C" __global__ void log_returns_kernel(
    const float* __restrict__ prices,
    float* __restrict__ output,
    int n)
{
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= n) return;

    if (idx == 0) {
        output[0] = make_nanf();
        return;
    }

    output[idx] = logf(prices[idx] / prices[idx - 1]);
}

extern "C" void launch_log_returns(
    const float* d_prices, float* d_output, int n)
{
    int blocks = (n + THREADS_PER_BLOCK - 1) / THREADS_PER_BLOCK;
    log_returns_kernel<<<blocks, THREADS_PER_BLOCK>>>(d_prices, d_output, n);
}

cmake_minimum_required(VERSION 3.20)
project(cudaquant_kernels LANGUAGES CXX CUDA)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CUDA_STANDARD 17)
set(CMAKE_CUDA_ARCHITECTURES 87)  # Orin SM 8.7

# Find CUDA toolkit
find_package(CUDAToolkit REQUIRED)

# Collect all kernel sources
file(GLOB KERNEL_SOURCES kernels/*.cu)

# Build shared library
add_library(cudaquant_kernels SHARED ${KERNEL_SOURCES})

target_include_directories(cudaquant_kernels PRIVATE ${CUDAToolkit_INCLUDE_DIRS})
target_link_libraries(cudaquant_kernels PRIVATE CUDA::cudart)

# Set output to lib/ directory
set_target_properties(cudaquant_kernels PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}/lib"
)

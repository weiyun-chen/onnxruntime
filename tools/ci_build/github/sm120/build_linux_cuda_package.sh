#!/bin/bash
# Build ONNX Runtime with CUDA 12.8 and SM120 support inside an NVIDIA CUDA container.
# Environment variables consumed:
#   CUDA_ARCHITECTURES  – semicolon-separated CUDA arch list (e.g. "80-real;120-real;120-virtual")
#   EXPECTED_SMS        – space-separated SM tags to verify (e.g. "sm_80 sm_120")
#   ORT_PARALLEL        – value passed to --parallel (default: 4)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
BUILD_DIR=/work/build
INSTALL_DIR=/work/install
ARTIFACTS_DIR="${REPO_ROOT}/artifacts"

: "${CUDA_ARCHITECTURES:=80-real;86-real;90-real;120-real;120-virtual}"
: "${EXPECTED_SMS:=sm_80 sm_86 sm_90 sm_120}"
: "${ORT_PARALLEL:=4}"

echo "=== Installing build tools ==="
apt-get update -qq
apt-get install -y --no-install-recommends git zip > /dev/null
pip install --disable-pip-version-check cmake==3.31.6 ninja==1.11.1.3 packaging==24.2

echo "=== Building ONNX Runtime ==="
python "${REPO_ROOT}/tools/ci_build/build.py" \
    --allow_running_as_root \
    --update \
    --build \
    --build_dir "${BUILD_DIR}" \
    --config Release \
    --cmake_generator Ninja \
    --skip_submodule_sync \
    --skip_tests \
    --parallel "${ORT_PARALLEL}" \
    --build_shared_lib \
    --enable_lto \
    --use_cuda \
    --cuda_home /usr/local/cuda \
    --cudnn_home /usr \
    --cmake_extra_defines \
        "CMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES}" \
        "onnxruntime_USE_FPA_INTB_GEMM=OFF"

echo "=== Installing build output ==="
cmake --install "${BUILD_DIR}/Release" --config Release --prefix "${INSTALL_DIR}"

echo "=== Verifying CUDA architectures ==="
PROVIDER_LIB="${BUILD_DIR}/Release/libonnxruntime_providers_cuda.so"
ELF_LIST="$(cuobjdump --list-elf "${PROVIDER_LIB}" 2>&1 || true)"
echo "${ELF_LIST}"
for sm in ${EXPECTED_SMS}; do
    if ! echo "${ELF_LIST}" | grep -q "${sm}"; then
        echo "ERROR: ${PROVIDER_LIB} does not contain ${sm} code" >&2
        exit 1
    fi
done
PTX_LIST="$(cuobjdump --list-ptx "${PROVIDER_LIB}" 2>&1 || true)"
echo "${PTX_LIST}"
if ! echo "${PTX_LIST}" | grep -q "PTX"; then
    echo "ERROR: ${PROVIDER_LIB} does not contain compute_120 PTX" >&2
    exit 1
fi

echo "=== Packaging ==="
VERSION="$(cat "${REPO_ROOT}/VERSION_NUMBER" | tr -d '[:space:]')"
COMMIT="${GITHUB_SHA:-$(git -C "${REPO_ROOT}" rev-parse HEAD)}"
PACKAGE_NAME="onnxruntime-linux-x64-gpu-${VERSION}-sm120"

python "${REPO_ROOT}/tools/ci_build/github/sm120/package_cuda_release.py" \
    --platform linux \
    --source-dir "${REPO_ROOT}" \
    --install-dir "${INSTALL_DIR}" \
    --build-output-dir "${BUILD_DIR}/Release" \
    --output-dir "${ARTIFACTS_DIR}" \
    --package-name "${PACKAGE_NAME}" \
    --commit "${COMMIT}"

echo "=== Done. Artifacts in ${ARTIFACTS_DIR} ==="
ls -lh "${ARTIFACTS_DIR}"

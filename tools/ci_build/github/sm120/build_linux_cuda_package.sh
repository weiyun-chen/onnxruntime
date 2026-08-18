#!/usr/bin/env bash
set -euo pipefail

: "${CUDA_ARCHITECTURES:?Set CUDA_ARCHITECTURES (semicolon-separated CMake architecture list)}"
: "${EXPECTED_SMS:?Set EXPECTED_SMS (space-separated, for example sm_60 sm_75 sm_120)}"

SOURCE_DIR="${SOURCE_DIR:-/src}"
WORK_DIR="${WORK_DIR:-/work}"
OUTPUT_DIR="${OUTPUT_DIR:-${SOURCE_DIR}/artifacts}"
PARALLEL="${ORT_PARALLEL:-2}"
BUILD_DIR="${WORK_DIR}/build"
INSTALL_DIR="${WORK_DIR}/install"

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install --yes --no-install-recommends \
  build-essential ca-certificates git python3 python3-pip zip
rm -rf /var/lib/apt/lists/*
python3 -m pip install --no-cache-dir \
  cmake==3.31.6 ninja==1.11.1.3 packaging==24.2

python3 "${SOURCE_DIR}/tools/ci_build/build.py" \
  --allow_running_as_root \
  --update \
  --build \
  --build_dir "${BUILD_DIR}" \
  --config Release \
  --cmake_generator Ninja \
  --skip_submodule_sync \
  --skip_tests \
  --parallel "${PARALLEL}" \
  --build_shared_lib \
  --enable_lto \
  --use_cuda \
  --cuda_home /usr/local/cuda \
  --cudnn_home /usr \
  --cmake_extra_defines \
    "CMAKE_CUDA_ARCHITECTURES=${CUDA_ARCHITECTURES}" \
    "onnxruntime_USE_FPA_INTB_GEMM=OFF"

PROVIDER_LIBRARY="${BUILD_DIR}/Release/libonnxruntime_providers_cuda.so"
test -f "${PROVIDER_LIBRARY}"
cuobjdump --list-elf "${PROVIDER_LIBRARY}" | tee "${WORK_DIR}/cuda-architectures.txt"
read -r -a expected_sms <<< "${EXPECTED_SMS}"
for expected_sm in "${expected_sms[@]}"; do
  grep -Eq "${expected_sm}([a-z])?" "${WORK_DIR}/cuda-architectures.txt"
done
cuobjdump --list-ptx "${PROVIDER_LIBRARY}" | tee "${WORK_DIR}/cuda-ptx.txt"
grep -Eiq 'PTX' "${WORK_DIR}/cuda-ptx.txt"

cmake --install "${BUILD_DIR}/Release" --prefix "${INSTALL_DIR}" --strip

VERSION="$(tr -d '[:space:]' < "${SOURCE_DIR}/VERSION_NUMBER")"
PACKAGE_NAME="onnxruntime-linux-x64-gpu-${VERSION}-sm120"
COMMIT="$(git -C "${SOURCE_DIR}" rev-parse HEAD)"
python3 "${SOURCE_DIR}/tools/ci_build/github/sm120/package_cuda_release.py" \
  --platform linux \
  --source-dir "${SOURCE_DIR}" \
  --install-dir "${INSTALL_DIR}" \
  --output-dir "${OUTPUT_DIR}" \
  --package-name "${PACKAGE_NAME}" \
  --commit "${COMMIT}"

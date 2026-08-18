# CUDA 12.8 release packages with SM120

The `CUDA 12.8 release packages with SM120` GitHub Actions workflow builds
native C/C++ packages for these targets:

| Target | Toolkit | CUDA architectures | Archive |
|---|---:|---|---|
| Windows x64 | 12.8.1 | `sm_61`, `sm_75`, `sm_86`, `sm_89`, `sm_120a` + `compute_120` PTX | `.zip` |
| Linux x64 | 12.8.1 | `sm_60`, `sm_70`, `sm_75`, `sm_80`, `sm_86`, `sm_90a`, `sm_120a` + `compute_120` PTX | `.tgz` |

These lists follow the CUDA 12.8 package profiles introduced by upstream PR
#29711, including the older targets selected by each official package pipeline
and adding SM120 as both native code and forward-compatible PTX. This is a
broad-compatibility release rather than an SM120-only compact build, so the CUDA
provider and final archives will be significantly larger.

The output filenames are:

- `onnxruntime-win-x64-gpu-1.23.2-sm120.zip`
- `onnxruntime-win-x64-gpu-1.23.2-sm120-symbols.zip`
- `onnxruntime-linux-x64-gpu-1.23.2-sm120.tgz`

The archives use the same top-level layout as ONNX Runtime native releases:
`include/`, `lib/`, release metadata, and no build tree. Windows PDB files are
placed in a separate `-symbols.zip`, so the runtime/development ZIP remains
smaller than an archive containing all PDB files.
Linux uses `.tgz` to preserve the `libonnxruntime.so` symbolic links, matching
the official Linux release format. The
[official v1.23.2 release](https://github.com/microsoft/onnxruntime/releases/tag/v1.23.2)
likewise uses a ZIP for its Windows GPU asset and a TGZ for its Linux GPU asset.
These custom packages contain the CUDA Execution Provider but not the optional
TensorRT Execution Provider, and the `-sm120` suffix makes that compatibility
difference explicit.

Upstream [PR #29711](https://github.com/microsoft/onnxruntime/pull/29711) was
merged for ONNX Runtime 1.28.0, not 1.23.2. This workflow backports its CUDA 12.8
architecture profiles: `61;75;86;89;120` on Windows and
`60;70;75;80;86;90;120` on Linux, with `120-virtual` as the sole PTX target. It
does not backport unrelated kernel or runtime fixes from newer ONNX Runtime
releases. This branch's CUDA CMake normalization upgrades the real SM90 and
SM120 targets to accelerated `90a-real` and `120a-real` targets.

Linux aarch64 is intentionally not produced. CUDA 12.8's aarch64 compiler can
generate SM120 device code, but ONNX Runtime v1.23.2 did not publish an official
Linux aarch64 GPU archive, and an ARM64 host plus GeForce Blackwell runtime
requires a separately validated driver/hardware setup.

Run the workflow manually from the Actions page to download workflow artifacts.
To create a GitHub Release and attach all packages, push a matching tag:

```bash
git tag v1.23.2-sm120
git push origin v1.23.2-sm120
```

No GPU is required on the runners. `cuobjdump` verifies that the compiled CUDA
provider contains the requested architecture before packaging succeeds. The
workflow removes unused Android, .NET, GHC, and CodeQL installations only from
the disposable hosted runners to make room for the CUDA images and build tree.

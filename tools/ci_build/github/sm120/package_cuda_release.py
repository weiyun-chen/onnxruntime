"""Package ONNX Runtime CUDA release artifacts into a platform ZIP.

This script collects the shared libraries and headers produced by a Release
build and bundles them together with a manifest file that records the version
and commit SHA.
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_linux(install_dir: Path, build_output_dir: Path, staging: Path) -> None:
    lib_dst = staging / "lib"
    inc_dst = staging / "include"
    lib_dst.mkdir(parents=True, exist_ok=True)
    inc_dst.mkdir(parents=True, exist_ok=True)

    # Shared libraries from install tree
    install_lib = install_dir / "lib"
    if install_lib.is_dir():
        for f in install_lib.glob("libonnxruntime*.so*"):
            shutil.copy2(f, lib_dst / f.name)

    # Provider shared libraries may live in the build output directory
    for f in build_output_dir.glob("libonnxruntime_providers*.so*"):
        dst = lib_dst / f.name
        if not dst.exists():
            shutil.copy2(f, dst)

    # Headers
    install_inc = install_dir / "include"
    if install_inc.is_dir():
        shutil.copytree(install_inc, inc_dst, dirs_exist_ok=True)


def _collect_windows(install_dir: Path, build_output_dir: Path, staging: Path) -> None:
    lib_dst = staging / "lib"
    inc_dst = staging / "include"
    lib_dst.mkdir(parents=True, exist_ok=True)
    inc_dst.mkdir(parents=True, exist_ok=True)

    for f in (install_dir / "bin").glob("onnxruntime*.dll"):
        shutil.copy2(f, lib_dst / f.name)
    for f in (install_dir / "lib").glob("onnxruntime*.lib"):
        shutil.copy2(f, lib_dst / f.name)

    # Provider DLLs may live directly in the build output dir
    for f in build_output_dir.glob("onnxruntime_providers*.dll"):
        dst = lib_dst / f.name
        if not dst.exists():
            shutil.copy2(f, dst)

    install_inc = install_dir / "include"
    if install_inc.is_dir():
        shutil.copytree(install_inc, inc_dst, dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Package an ONNX Runtime CUDA release build")
    parser.add_argument("--platform", required=True, choices=("linux", "windows"))
    parser.add_argument("--source-dir", required=True, type=Path, help="Repository root")
    parser.add_argument("--install-dir", required=True, type=Path, help="cmake --install prefix")
    parser.add_argument("--build-output-dir", required=True, type=Path, help="CMake binary dir for Release config")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory to write the ZIP into")
    parser.add_argument("--package-name", required=True, help="Base name for the output ZIP (without .zip)")
    parser.add_argument("--commit", default="", help="Git commit SHA to embed in the manifest")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Staging area
    staging = args.output_dir / args.package_name
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    # Collect platform-specific files
    if args.platform == "linux":
        _collect_linux(args.install_dir, args.build_output_dir, staging)
    else:
        _collect_windows(args.install_dir, args.build_output_dir, staging)

    # Version number
    version_file = args.source_dir / "VERSION_NUMBER"
    version = version_file.read_text().strip() if version_file.exists() else "unknown"

    # Manifest
    file_hashes: dict[str, str] = {}
    for f in sorted(staging.rglob("*")):
        if f.is_file():
            rel = f.relative_to(staging).as_posix()
            file_hashes[rel] = _sha256(f)

    manifest = {
        "version": version,
        "commit": args.commit,
        "platform": args.platform,
        "package": args.package_name,
        "files": file_hashes,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, indent=2))

    # Create ZIP
    zip_path = args.output_dir / f"{args.package_name}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(staging.rglob("*")):
            if f.is_file():
                zf.write(f, f.relative_to(args.output_dir))

    # Clean staging tree (keep only the ZIP)
    shutil.rmtree(staging)

    print(f"Created {zip_path} ({zip_path.stat().st_size / 1024 / 1024:.1f} MB)")
    sys.exit(0)


if __name__ == "__main__":
    main()

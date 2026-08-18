#!/usr/bin/env python3
"""Create an ONNX Runtime CUDA C API release archive.

The archive layout intentionally follows the native packages published by
ONNX Runtime. It contains the installed public headers, shared libraries and
release metadata, but not the build tree or static intermediate libraries.
"""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path


METADATA_FILES = ("README.md", "LICENSE", "ThirdPartyNotices.txt", "VERSION_NUMBER")
WINDOWS_REQUIRED_FILES = (
    "onnxruntime.dll",
    "onnxruntime.lib",
    "onnxruntime_providers_shared.dll",
    "onnxruntime_providers_shared.lib",
    "onnxruntime_providers_cuda.dll",
    "onnxruntime_providers_cuda.lib",
)
LINUX_REQUIRED_FILES = (
    "libonnxruntime_providers_shared.so",
    "libonnxruntime_providers_cuda.so",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--build-output-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-name", required=True)
    parser.add_argument("--commit", required=True)
    return parser.parse_args()


def require_path(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required package input does not exist: {path}")
    return path


def copy_metadata(source_dir: Path, package_dir: Path, commit: str) -> None:
    for filename in METADATA_FILES:
        shutil.copy2(require_path(source_dir / filename), package_dir / filename)
    privacy = source_dir / "docs" / "Privacy.md"
    if privacy.exists():
        shutil.copy2(privacy, package_dir / privacy.name)
    (package_dir / "GIT_COMMIT_ID").write_text(f"{commit}\n", encoding="utf-8")


def copy_public_headers(install_dir: Path, package_dir: Path) -> None:
    installed_headers = require_path(install_dir / "include" / "onnxruntime")
    shutil.copytree(installed_headers, package_dir / "include", symlinks=True)


def find_library_dir(install_dir: Path) -> Path:
    for dirname in ("lib", "lib64"):
        candidate = install_dir / dirname
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError(f"No lib or lib64 directory found below {install_dir}")


def make_windows_package(args: argparse.Namespace, package_dir: Path) -> Path | None:
    output_lib = package_dir / "lib"
    output_lib.mkdir()

    install_bin = require_path(args.install_dir / "bin")
    install_lib = find_library_dir(args.install_dir)
    for filename in WINDOWS_REQUIRED_FILES:
        source = (
            install_bin / filename
            if filename.endswith(".dll")
            else install_lib / filename
        )
        shutil.copy2(require_path(source), output_lib / filename)

    if args.build_output_dir is None:
        return None

    pdb_files = sorted(args.build_output_dir.glob("onnxruntime*.pdb"))
    if not pdb_files:
        return None

    symbols_dir = package_dir.parent / f"{args.package_name}-symbols"
    symbols_dir.mkdir()
    for pdb_file in pdb_files:
        shutil.copy2(pdb_file, symbols_dir / pdb_file.name)
    (symbols_dir / "GIT_COMMIT_ID").write_text(f"{args.commit}\n", encoding="utf-8")
    return symbols_dir


def make_linux_package(args: argparse.Namespace, package_dir: Path) -> None:
    install_lib = find_library_dir(args.install_dir)
    output_lib = package_dir / "lib"
    shutil.copytree(install_lib, output_lib, symlinks=True)
    for filename in LINUX_REQUIRED_FILES:
        require_path(output_lib / filename)

    # libonnxruntime.so is versioned on Linux. Require both the link-time name
    # and at least one versioned runtime file/symlink.
    require_path(output_lib / "libonnxruntime.so")
    if not list(output_lib.glob("libonnxruntime.so.*")):
        raise FileNotFoundError("No versioned libonnxruntime.so was installed")


def make_zip(source_dir: Path, archive: Path) -> None:
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as output:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(source_dir.parent))


def make_tgz(source_dir: Path, archive: Path) -> None:
    with tarfile.open(archive, "w:gz", compresslevel=9) as output:
        output.dereference = False
        output.add(source_dir, arcname=source_dir.name, recursive=True)


def main() -> None:
    args = parse_args()
    args.source_dir = args.source_dir.resolve()
    args.install_dir = args.install_dir.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ort-cuda-package-") as temp:
        staging_dir = Path(temp)
        package_dir = staging_dir / args.package_name
        package_dir.mkdir()

        copy_public_headers(args.install_dir, package_dir)
        copy_metadata(args.source_dir, package_dir, args.commit)

        symbols_dir = None
        if args.platform == "windows":
            symbols_dir = make_windows_package(args, package_dir)
            archive = args.output_dir / f"{args.package_name}.zip"
            make_zip(package_dir, archive)
        else:
            make_linux_package(args, package_dir)
            archive = args.output_dir / f"{args.package_name}.tgz"
            make_tgz(package_dir, archive)

        if symbols_dir is not None:
            make_zip(symbols_dir, args.output_dir / f"{symbols_dir.name}.zip")

    print(f"Created {archive} ({archive.stat().st_size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()

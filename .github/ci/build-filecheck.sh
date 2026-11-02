#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# Builds FileCheck from the llvm-project source release that filecheck.json pins, into
# DESTINATION/bin. CI runs it when its cache has no FileCheck for the runner image, so every row
# uses the same FileCheck; it runs the same way locally:
#
#   .github/ci/build-filecheck.sh .forge/ci/filecheck
#
# Only llvm/, cmake/, third-party/ and libc/ (whose headers LLVM's Support library includes) are
# extracted, without their tests, and only the FileCheck target is built. cmake picks its default generator: Makefiles, or the newest Visual Studio on
# Windows, which finds MSVC without vcvarsall.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $0 DESTINATION" >&2
    exit 2
fi
destination=$1
here=$(cd "$(dirname "$0")" && pwd)
version=$(jq -r .version "$here/filecheck.json")
url=$(jq -r .url "$here/filecheck.json" | sed "s/{version}/$version/g")
sha256=$(jq -r .sha256 "$here/filecheck.json")

work=${RUNNER_TEMP:-${TMPDIR:-/tmp}}/forge-filecheck-$version
binary=FileCheck
tar_options=()
case "$(uname -s)" in
    MINGW* | MSYS* | CYGWIN*)
        # Git Bash: D:/a/... paths suit both its tools and native cmake, and its GNU tar would
        # take the D: of an archive path for a remote host.
        work=$(cygpath -m "$work")
        binary=FileCheck.exe
        tar_options=(--force-local)
        ;;
esac
source=llvm-project-$version.src
archive=$work/$source.tar.xz
mkdir -p "$work"

if [ ! -f "$archive" ]; then
    echo "downloading $url"
    curl -fsSL --retry 3 -o "$archive.part" "$url"
    mv "$archive.part" "$archive"
fi
if command -v sha256sum >/dev/null; then
    actual=$(sha256sum "$archive" | cut -d' ' -f1)
else
    actual=$(shasum -a 256 "$archive" | cut -d' ' -f1)
fi
if [ "$actual" != "$sha256" ]; then
    echo "error: $archive has sha256 $actual, but filecheck.json pins $sha256" >&2
    rm -f "$archive"
    exit 1
fi

rm -rf "${work:?}/$source" "$work/build"
# The only symlinks, which Windows cannot always create, are the scripts in llvm/utils/mlgo-utils.
excludes=(--exclude="$source/llvm/utils/mlgo-utils/*.py")
for project in llvm libc; do
    for directory in test unittests docs benchmarks fuzzing; do
        excludes+=(--exclude="$source/$project/$directory")
    done
done
tar ${tar_options[@]+"${tar_options[@]}"} -xf "$archive" -C "$work" "${excludes[@]}" \
    "$source/llvm" "$source/libc" "$source/cmake" "$source/third-party"

cmake -S "$work/$source/llvm" -B "$work/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DLLVM_TARGETS_TO_BUILD=host \
    -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF \
    -DLLVM_INCLUDE_DOCS=OFF -DLLVM_ENABLE_BINDINGS=OFF \
    -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_LIBXML2=OFF \
    -DLLVM_ENABLE_LIBEDIT=OFF -DLLVM_ENABLE_LIBPFM=OFF
cmake --build "$work/build" --config Release --target FileCheck --parallel

built=$(find "$work/build" -type f -name "$binary" -path "*bin*" | head -n 1)
if [ -z "$built" ]; then
    echo "error: the build produced no $binary" >&2
    exit 1
fi
mkdir -p "$destination/bin"
cp "$built" "$destination/bin/$binary"
"$destination/bin/$binary" --version
rm -rf "${work:?}/$source" "$work/build"

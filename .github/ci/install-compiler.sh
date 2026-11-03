#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# Makes one matrix row's compiler available and checks that it is the version the row expects, so
# that a runner image changing its compilers fails the row instead of quietly testing another one.
# It installs only what the image lacks. The row comes from the environment:
#
#   ROW_FAMILY  gcc, clang, apple or msvc
#   ROW_CXX     the C++ compiler for gcc, clang and apple (g++-13, clang++-23, clang++)
#   ROW_XCODE   the Xcode version for apple, selected with DEVELOPER_DIR
#   ROW_EXPECT  what the compiler's version must start with: "13.", "21.", "19.44"
set -euo pipefail

# The fingerprint of the key apt.llvm.org signs with, checked before the key is trusted.
LLVM_KEY_FINGERPRINT=6084F3CF814B57C1CF12EFD515CF4D18AF4F7421

fail() {
    echo "::error::$*"
    exit 1
}

as_root() {
    if [ "$(id -u)" = 0 ]; then "$@"; else sudo "$@"; fi
}

install_from_apt_llvm_org() {
    local major=$1 codename key
    codename=$(. /etc/os-release && echo "$VERSION_CODENAME")
    key=$(mktemp)
    curl -fsSL --retry 3 -o "$key" https://apt.llvm.org/llvm-snapshot.gpg.key
    local fingerprint
    fingerprint=$(gpg --show-keys --with-colons "$key" | awk -F: '$1 == "fpr" { print $10; exit }')
    [ "$fingerprint" = "$LLVM_KEY_FINGERPRINT" ] ||
        fail "apt.llvm.org's key has fingerprint $fingerprint, expected $LLVM_KEY_FINGERPRINT"
    gpg --dearmor < "$key" | as_root tee /usr/share/keyrings/apt-llvm-org.gpg > /dev/null
    echo "deb [signed-by=/usr/share/keyrings/apt-llvm-org.gpg] https://apt.llvm.org/$codename/ llvm-toolchain-$codename-$major main" |
        as_root tee /etc/apt/sources.list.d/apt-llvm-org.list > /dev/null
    as_root apt-get update -q
    # llvm-N has llvm-ar-N and the LTO linker plugin; libclang-rt-N-dev has the sanitizers'
    # runtimes and headers, which clang-N alone lacks.
    as_root apt-get install -y -q --no-install-recommends "clang-$major" "llvm-$major" "lld-$major" \
        "libclang-rt-$major-dev"
}

case "$ROW_FAMILY" in
    gcc)
        if ! command -v "$ROW_CXX" > /dev/null; then
            as_root apt-get update -q
            as_root apt-get install -y -q --no-install-recommends "$ROW_CXX"
        fi
        version=$("$ROW_CXX" -dumpfullversion)
        ;;
    clang)
        if ! command -v "$ROW_CXX" > /dev/null || ! command -v "${ROW_CXX/clang++/llvm-ar}" > /dev/null; then
            install_from_apt_llvm_org "${ROW_CXX#clang++-}"
        fi
        version=$("$ROW_CXX" -dumpversion)
        ;;
    apple)
        developer_dir=/Applications/Xcode_$ROW_XCODE.app/Contents/Developer
        [ -d "$developer_dir" ] || fail "this image has no Xcode $ROW_XCODE ($developer_dir)"
        echo "DEVELOPER_DIR=$developer_dir" >> "$GITHUB_ENV"
        export DEVELOPER_DIR=$developer_dir
        version=$("$ROW_CXX" -dumpversion)
        ;;
    msvc)
        # x uses the newest Visual Studio with the x64 C++ tools, and vcvarsall's default toolset;
        # MSVC's toolset 14.N is cl 19.N.
        vswhere="/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe"
        installation=$(cygpath -u "$("$vswhere" -latest -products '*' -requires \
            Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath | tr -d '\r')")
        toolset=$(tr -d '\r' < "$installation/VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt")
        version=19.$(echo "$toolset" | cut -d. -f2)
        ;;
    *)
        fail "unknown compiler family '$ROW_FAMILY'"
        ;;
esac

case "$version" in
    "$ROW_EXPECT"*) echo "compiler: $ROW_FAMILY $version" ;;
    *) fail "the $ROW_FAMILY compiler is $version, but the row expects $ROW_EXPECT: update .github/ci/matrix.json or the runner" ;;
esac

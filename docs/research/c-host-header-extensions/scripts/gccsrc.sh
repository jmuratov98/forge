#!/bin/sh
# Fetch the GCC 15.2.0 source files whose tables define the name universe,
# plus Ubuntu's packaging patches, so we can tell whether Ubuntu touched them.
# usage (in the VM): sh gccsrc.sh OUTDIR
set -eu
out=$1
mkdir -p "$out/src" "$out/ubuntu"
# The GNU release tarball (gcc.gnu.org's gitweb rate-limits blob downloads).
rel=https://ftp.gnu.org/gnu/gcc/gcc-15.2.0
[ -s "$out/gcc-15.2.0.tar.xz" ] || curl -sSfL "$rel/gcc-15.2.0.tar.xz" -o "$out/gcc-15.2.0.tar.xz"
curl -sSfL "$rel/gcc-15.2.0.tar.xz.sig" -o "$out/gcc-15.2.0.tar.xz.sig"
curl -sSfL https://ftp.gnu.org/gnu/gnu-keyring.gpg -o "$out/gnu-keyring.gpg"
( cd "$out" && gpgv --keyring ./gnu-keyring.gpg gcc-15.2.0.tar.xz.sig gcc-15.2.0.tar.xz > tarball-check.txt 2>&1;
  sha256sum gcc-15.2.0.tar.xz >> tarball-check.txt )
for f in gcc/c-family/c-common.cc gcc/c-family/c-common.h gcc/builtins.def gcc/sync-builtins.def \
         gcc/builtin-attrs.def gcc/c-family/c-attribs.cc gcc/c-family/c-pragma.cc \
         gcc/c-family/c-lex.cc gcc/c-family/c-cppbuiltin.cc gcc/c/c-decl.cc gcc/c/c-parser.cc \
         gcc/config/aarch64/aarch64.cc gcc/config/aarch64/aarch64-builtins.cc \
         gcc/config/aarch64/aarch64-c.cc gcc/config/aarch64/aarch64-sve-builtins.cc \
         gcc/config/glibc-c.cc gcc/config/linux.h gcc/config/aarch64/aarch64-linux.h \
         libcpp/directives.cc libcpp/init.cc libcpp/expr.cc libcpp/macro.cc libcpp/pch.cc \
         gcc/ginclude/stddef.h gcc/ginclude/stdarg.h gcc/glimits.h gcc/BASE-VER gcc/DATESTAMP; do
  echo "gcc-15.2.0/$f"
done > "$out/members.txt"
tar -xJf "$out/gcc-15.2.0.tar.xz" -C "$out/src" --strip-components=1 -T "$out/members.txt"
( cd "$out/src" && find . -type f | LC_ALL=C sort | xargs sha256sum > ../src-sha256.txt )
# Ubuntu's packaging (patches are applied at build time)
pool=http://archive.ubuntu.com/ubuntu/pool/main/g/gcc-15
for f in gcc-15_15.2.0-16ubuntu1.dsc gcc-15_15.2.0-16ubuntu1.debian.tar.xz; do
  [ -s "$out/ubuntu/$f" ] || curl -sSfL "$pool/$f" -o "$out/ubuntu/$f"
done
( cd "$out/ubuntu" && sha256sum * > ../ubuntu-sha256.txt && rm -rf debian && tar -xJf gcc-15_15.2.0-16ubuntu1.debian.tar.xz )
# Which Ubuntu/Debian patches touch the files above?
( cd "$out/src" && find . -type f | sed 's|^\./||' ) > "$out/files.txt"
: > "$out/ubuntu-patch-hits.txt"
for p in "$out"/ubuntu/debian/patches/*.diff "$out"/ubuntu/debian/patches/*.patch; do
  [ -f "$p" ] || continue
  while read -r f; do
    if grep -qE "^\+\+\+ [^ ]*/$f([[:space:]]|$)" "$p"; then
      echo "$(basename "$p") $f" >> "$out/ubuntu-patch-hits.txt"
    fi
  done < "$out/files.txt"
done
wc -l "$out/ubuntu-patch-hits.txt"

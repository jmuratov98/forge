#!/bin/sh
# Record the VM's toolchain facts. Run inside the VM: sh facts.sh OUTDIR
# (The VM was made with: limactl create --name=forge-c13 --cpus=4 --memory=8
#  --tty=false template:ubuntu-26.04; limactl start forge-c13; then
#  sudo apt-get install gcc-15=15.2.0-16ubuntu1 linux-libc-dev=7.0.0-43.43
#  libc6-dev=2.43-2ubuntu2.4.)
set -eu
out=$1
mkdir -p "$out/predef" "$out/debs"
cat /etc/os-release > "$out/os-release.txt"
uname -a > "$out/uname.txt"
dpkg -l gcc-15 cpp-15 gcc-15-aarch64-linux-gnu cpp-15-aarch64-linux-gnu \
  libgcc-15-dev libc6-dev linux-libc-dev libc6 > "$out/dpkg-l.txt"
sudo dpkg --verify libc6-dev linux-libc-dev libgcc-15-dev \
  gcc-15-aarch64-linux-gnu cpp-15-aarch64-linux-gnu > "$out/dpkg-verify.txt" 2>&1 || true
( cd "$out/debs" && apt-get download libc6-dev=2.43-2ubuntu2.4 linux-libc-dev=7.0.0-43.43 \
    gcc-15=15.2.0-16ubuntu1 libgcc-15-dev=15.2.0-16ubuntu1 cpp-15=15.2.0-16ubuntu1 \
    gcc-15-aarch64-linux-gnu=15.2.0-16ubuntu1 cpp-15-aarch64-linux-gnu=15.2.0-16ubuntu1 \
    >/dev/null 2>&1 && sha256sum *.deb > ../deb-sha256.txt && apt-cache policy \
    libc6-dev linux-libc-dev gcc-15 > ../apt-policy.txt )
gcc-15 -v > "$out/gcc-v.txt" 2>&1
gcc-15 -dumpspecs > "$out/dumpspecs.txt"
gcc-15 -O0 -v -E -x c /dev/null -o /dev/null > "$out/v-E-O0.txt" 2>&1
gcc-15 -O2 -v -E -x c /dev/null -o /dev/null > "$out/v-E-O2.txt" 2>&1
readlink -f "$(command -v gcc-15)" > "$out/gcc-15-path.txt"
for cfg in "gnu89:-std=gnu89" "gnu89+gs:-std=gnu89 -D_GNU_SOURCE" \
           "gnu99:-std=gnu99" "gnu99+gs:-std=gnu99 -D_GNU_SOURCE" \
           "gnu17:-std=gnu17" "gnu17+gs:-std=gnu17 -D_GNU_SOURCE" \
           "gnu23:" "gnu23+gs:-D_GNU_SOURCE" "gnu23-explicit:-std=gnu23"; do
  name=${cfg%%:*}; flags=${cfg#*:}
  # shellcheck disable=SC2086
  gcc-15 -O0 $flags -E -dM -x c /dev/null | LC_ALL=C sort > "$out/predef/$name.txt"
done
diff "$out/predef/gnu23.txt" "$out/predef/gnu23-explicit.txt" > "$out/predef/gnu23-vs-explicit.diff" \
  && echo "gnu23 default == -std=gnu23" > "$out/predef/gnu23-vs-explicit.txt" || true
# The undefined-at-O0 checks
for f in "$out"/predef/*.txt; do
  printf '%s OPTIMIZE=%s FORTIFY=%s\n' "$(basename "$f")" \
    "$(grep -c '^#define __OPTIMIZE__ ' "$f" || true)" \
    "$(grep -c '^#define _FORTIFY_SOURCE ' "$f" || true)"
done > "$out/predef/O0-checks.txt"

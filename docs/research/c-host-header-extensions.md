# C-mode host header extension inventory

Research for GitHub issue #13 (parent map #1, consumer #8). Throwaway branch `research/c-host-header-extensions`; never merged, no PR.

**Status: in progress.** Section 0 (VM and package facts) is complete; the data is in `c-host-header-extensions/data/facts/`.

## 0. Sources and versions

- Lima 2.2.1 VM `forge-c13` (vz, aarch64, 4 CPUs, 8 GiB), template `ubuntu-26.04`: Ubuntu 26.04.1 LTS, kernel 7.0.0-34-generic.
- Packages installed with apt from `http://archive.ubuntu.com/ubuntu` (the template's mirror): gcc-15 15.2.0-16ubuntu1, libc6-dev 2.43-2ubuntu2.4, linux-libc-dev 7.0.0-43.43, libgcc-15-dev 15.2.0-16ubuntu1. The .deb SHA256s (`data/facts/deb-sha256.txt`) equal those in #9's section 0. `dpkg --verify` reports no changed file.

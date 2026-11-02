# SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

# The lit suite for everything observable from outside a library: forge's build (build/), the
# compile-time contracts of its headers (host/), and later its tools. premake writes a
# lit.site.cfg.py for every configuration, which sets the forge_* values below and then loads this
# file, so lit runs on a configuration's directory: lit -sv build/Debug/test

import os
import platform
import shutil

import lit.formats

if not hasattr(config, "forge_source_root"):
    lit_config.fatal(
        "run lit on a configuration's test directory, such as build/Debug/test; premake writes "
        "the lit.site.cfg.py there"
    )

config.name = "forge"
# The internal shell runs RUN lines the same way on every host, Windows included.
config.test_format = lit.formats.ShTest(execute_external=False)
config.test_source_root = os.path.dirname(__file__)
# Each directory's lit.local.cfg says which of its files are tests; Inputs/ holds what they read.
config.suffixes = []
config.excludes = ["Inputs"]

config.environment["LC_ALL"] = "C"


def quote(argument):
    """Quotes one argument for a RUN line, which the internal shell splits like a POSIX shell."""
    if argument and not any(c in argument for c in " \t\"'\\$&|;<>()*?[]{}~#"):
        return argument
    return '"' + argument.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Features. How forge is built comes from premake, the same table that sets the build's defines;
# what it is built on is detected here. "host" means the machine forge runs on, as in config.hpp.
config.available_features.update(config.forge_features)
config.available_features.add("host-cxx-" + config.forge_host_cxx_family)

host_systems = {"Darwin": "host-macos", "Linux": "host-linux", "Windows": "host-windows"}
if platform.system() in host_systems:
    config.available_features.add(host_systems[platform.system()])

host_machines = {
    "x86_64": "host-x86_64",
    "amd64": "host-x86_64",
    "arm64": "host-aarch64",
    "aarch64": "host-aarch64",
}
if platform.machine().lower() in host_machines:
    config.available_features.add(host_machines[platform.machine().lower()])

def substitute(pattern, text):
    """lit applies substitutions in order with re.sub, so a name that is a prefix of another must
    come after it. re.sub also reads backslashes in `text` as escapes; lit doubles them itself only
    on Windows."""
    if not lit_config.isWindows:
        text = text.replace("\\", "\\\\")
    config.substitutions.append((pattern, text))


msvc = config.forge_host_cxx_family == "msvc"
host_cxx = " ".join(quote(argument) for argument in config.forge_host_cxx)

# forge's exact consumer flags, with -U/-D after them to override a build macro.
substitute("%host_cxx_syntax", host_cxx + (" /nologo /Zs" if msvc else " -fsyntax-only"))
substitute("%host_werror", "/WX" if msvc else "-Werror")
substitute(
    "%premake", quote(config.forge_premake) + " --scripts=" + quote(config.forge_source_root)
)

# FileCheck is the one tool lit cannot supply. The lookbehind leaves alone words that only contain
# the name, such as a path or a --check-prefix value.
filecheck = os.environ.get("FORGE_FILECHECK") or shutil.which("FileCheck")
if not filecheck:
    lit_config.fatal("FileCheck not found: put it on PATH or set FORGE_FILECHECK to its path")
substitute(r"(?<![\w./\\-])FileCheck\b", quote(filecheck))

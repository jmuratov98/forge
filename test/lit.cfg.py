import os
import platform

import lit.formats

config.name = "forge"
config.test_format = lit.formats.ShTest(execute_external=False)
config.suffixes = [".test"]
config.excludes = ["Inputs"]
config.test_source_root = os.path.join(config.forge_source_dir, "test")
config.test_exec_root = os.path.join(config.forge_build_dir, "test")


def quoted(path):
    return '"%s"' % path if " " in path else path


# Tests see the host's toolchain and nothing else. The MSVC variables are what
# `cl` needs to find its headers and libraries.
for name in ("PATH", "PATHEXT", "HOME", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT",
             "SYSTEMDRIVE", "USERPROFILE", "COMSPEC", "DEVELOPER_DIR", "SDKROOT",
             "INCLUDE", "LIB", "LIBPATH", "VCINSTALLDIR", "VSINSTALLDIR",
             "WindowsSdkDir", "WindowsSDKVersion", "UniversalCRTSdkDir"):
    if name in os.environ:
        config.environment[name] = os.environ[name]

scripts = os.path.join(config.forge_source_dir, "scripts")
python = quoted(config.python_exe)
config.substitutions += [
    ("%forge_source_dir", config.forge_source_dir),
    ("%forge_build_dir", config.forge_build_dir),
    ("%forge", quoted(config.forge_exe)),
    ("%configure", quoted(config.cmake_exe) + " -G Ninja -DCMAKE_MAKE_PROGRAM=" + quoted(config.ninja_exe)),
    ("%ninja", quoted(config.ninja_exe)),
    ("%cmake", quoted(config.cmake_exe)),
    ("%ctest", quoted(config.ctest_exe)),
    ("%python", python),
    ("%scripts", scripts),
    ("%graph_check", python + " " + os.path.join(scripts, "check_target_graph.py") + " --cmake "
     + quoted(config.cmake_exe) + " --cmake-arg=-GNinja --cmake-arg=-DCMAKE_MAKE_PROGRAM="
     + quoted(config.ninja_exe)),
    ("%lit", python + ' -c "from lit.main import main; main()" -v --param forge_build_dir='
     + config.forge_build_dir),
    ("%selftest_compiler", os.path.join(config.forge_build_dir, "test", "e2e_selftest_compiler.json")),
]

config.available_features.add("system-" + platform.system().lower())
if config.clang_tidy_exe:
    config.available_features.add("clang-tidy")
    config.substitutions.append(("%clang_tidy", quoted(config.clang_tidy_exe)))

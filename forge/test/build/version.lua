-- premake writes the version to <location>/generated/forge/core/version.inc: the base version from
-- VERSION, the build timestamp (from SOURCE_DATE_EPOCH when it is set) and --bug-report-url, as
-- C++ string literals. Only core gets the generated directory as an include directory. A VERSION
-- that is not one line with a SemVer base version, a URL with a control character, or a
-- SOURCE_DATE_EPOCH that is not a number stops premake before it writes anything; forge-describe,
-- which ./x needs for its help, does not read VERSION.
--
-- RUN: rm -rf %t
-- RUN: env SOURCE_DATE_EPOCH=0 %premake --file=%s --to=%t/valid --cc=clang --os=linux "--bug-report-url=https://example.com/?q=\"x\"\\y" ninja
-- RUN: FileCheck %s --input-file=%t/valid/generated/forge/core/version.inc --check-prefix=INC
-- RUN: FileCheck %s --input-file=%t/valid/forge_core.ninja --check-prefix=CORE
-- RUN: FileCheck %s --input-file=%t/valid/forge_other.ninja --check-prefix=OTHER
-- RUN: %premake --file=%s --to=%t/now --cc=clang --os=linux --shared ninja
-- RUN: FileCheck %s --input-file=%t/now/generated/forge/core/version.inc --check-prefix=NOW
-- RUN: FileCheck %s --input-file=%t/now/forge.ninja --check-prefix=CORE
--
-- RUN: env CASE=missing not %premake --file=%s --to=%t/missing --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-VERSION
-- RUN: not cat %t/missing/build.ninja
-- RUN: env CASE=no-newline not %premake --file=%s --to=%t/no-newline --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-VERSION
-- RUN: env CASE=two-lines not %premake --file=%s --to=%t/two-lines --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-VERSION
-- RUN: env CASE=metadata not %premake --file=%s --to=%t/metadata --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-VERSION
-- RUN: env CASE=leading-zero not %premake --file=%s --to=%t/leading-zero --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-VERSION
-- RUN: env CASE=control-url not %premake --file=%s --to=%t/control-url --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-URL
-- RUN: env SOURCE_DATE_EPOCH=yesterday not %premake --file=%s --to=%t/epoch --cc=clang --os=linux ninja 2>&1 | FileCheck %s --check-prefix=BAD-EPOCH
-- RUN: env CASE=missing %premake --file=%s --to=%t/describe --no-tests forge-describe

-- INC:      #define FORGE_DETAIL_VERSION_BASE "1.2.3-fixture"
-- INC-NEXT: #define FORGE_DETAIL_VERSION_BUILD "19700101T000000Z"
-- INC-NEXT: #define FORGE_DETAIL_BUG_REPORT_URL "https://example.com/?q=\"x\"\\y"

-- NOW:      #define FORGE_DETAIL_VERSION_BUILD "{{[0-9]{8}T[0-9]{6}Z}}"
-- NOW-NEXT: #define FORGE_DETAIL_BUG_REPORT_URL ""{{$}}

-- CORE:  cxxflags_{{forge_core|forge}}_Debug = {{.*}} -Igenerated
-- OTHER: cxxflags_forge_other_Debug =
-- OTHER-NOT: generated

-- BAD-VERSION: forge: {{.*}}tree{{[/\\]}}VERSION must hold one line with a SemVer base version
-- BAD-URL:     --bug-report-url: the URL contains a control character
-- BAD-EPOCH:   SOURCE_DATE_EPOCH must be a whole number of seconds, not 'yesterday'

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "core", "other" })

local version_file = path.join(forge.root, "VERSION")
local versions = {
    ["no-newline"] = "1.2.3",
    ["two-lines"] = "1.2.3\n1.2.4\n",
    metadata = "1.2.3+build\n",
    ["leading-zero"] = "1.02.3\n",
}
local case = os.getenv("CASE")
if case == "missing" then
    os.remove(version_file)
elseif case == "control-url" then
    _OPTIONS["bug-report-url"] = "https://example.com/\tbugs"
elseif case then
    io.writefile(version_file, versions[case])
end

forge.emit({
    forge.component { "core" },
    forge.component { "other", dependencies = { "core" } },
}, third_party)

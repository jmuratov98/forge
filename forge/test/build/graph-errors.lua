-- forge.emit rejects a set of descriptions that is not a valid component graph, before it creates
-- any project. A cycle is reported with its path.
--
-- RUN: env CASE=not-a-list not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=NOT-A-LIST
-- RUN: env CASE=not-a-description not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=NOT-A-DESCRIPTION
-- RUN: env CASE=duplicate-component not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=DUPLICATE-COMPONENT
-- RUN: env CASE=duplicate-test not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=DUPLICATE-TEST
-- RUN: env CASE=undeclared not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=UNDECLARED
-- RUN: env CASE=test-undeclared not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=TEST-UNDECLARED
-- RUN: env CASE=cycle not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=CYCLE
-- RUN: env CASE=self-cycle not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=SELF-CYCLE

require "premake/options"
require "premake/forge"

workspace "fixture"
    configurations { "Debug" }
    location(_OPTIONS.to)

local cases = {
    -- NOT-A-LIST: forge: forge/premake5.lua must return a list of forge.component and forge.test values
    ["not-a-list"] = "core",

    -- NOT-A-DESCRIPTION: forge: forge/premake5.lua returned something that is not a forge.component or forge.test
    ["not-a-description"] = { 42 },

    -- DUPLICATE-COMPONENT: forge: component 'core' is declared twice
    ["duplicate-component"] = {
        forge.component { "core" },
        forge.component { "core" },
    },

    -- DUPLICATE-TEST: forge: test 'core' is declared twice
    ["duplicate-test"] = {
        forge.component { "core" },
        forge.test { "core", dependencies = { "core" } },
        forge.test { "core", dependencies = { "core" } },
    },

    -- UNDECLARED: forge: component 'ir' depends on 'core', which is not a declared component
    ["undeclared"] = {
        forge.component { "ir", dependencies = { "core" } },
    },

    -- TEST-UNDECLARED: forge: test 'ir' depends on 'ir', which is not a declared component
    ["test-undeclared"] = {
        forge.component { "core" },
        forge.test { "ir", dependencies = { "ir" } },
    },

    -- CYCLE: forge: dependency cycle: core -> ir -> codegen -> core
    ["cycle"] = {
        forge.component { "support" },
        forge.component { "core", dependencies = { "support", "ir" } },
        forge.component { "ir", dependencies = { "codegen" } },
        forge.component { "codegen", dependencies = { "core" } },
    },

    -- SELF-CYCLE: forge: dependency cycle: core -> core
    ["self-cycle"] = {
        forge.component { "core", dependencies = { "core" } },
    },
}

forge.emit(cases[os.getenv("CASE")], nil)

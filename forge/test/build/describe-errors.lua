-- forge.component and forge.test reject a malformed description, and the error points at the line
-- of the description, not into premake/forge.lua.
--
-- RUN: env CASE=not-a-table not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=NOT-A-TABLE
-- RUN: env CASE=no-name not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=NO-NAME
-- RUN: env CASE=bad-name not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=BAD-NAME
-- RUN: env CASE=positional not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=POSITIONAL
-- RUN: env CASE=unknown-key not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=UNKNOWN-KEY
-- RUN: env CASE=bad-dependency not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=BAD-DEPENDENCY
-- RUN: env CASE=duplicate-dependency not %premake --file=%s --to=%t ninja 2>&1 | FileCheck %s --check-prefix=DUPLICATE-DEPENDENCY

require "premake/options"
require "premake/forge"

workspace "fixture"
    configurations { "Debug" }
    location(_OPTIONS.to)

local case = os.getenv("CASE")
if case == "not-a-table" then
    -- NOT-A-TABLE: describe-errors.lua:[[@LINE+1]]: forge.component expects a table: forge.component { "name", ... }
    forge.component "core"
elseif case == "no-name" then
    -- NO-NAME: describe-errors.lua:[[@LINE+1]]: forge.component: the first entry must be a snake_case name, got 'nil'
    forge.component { dependencies = {} }
elseif case == "bad-name" then
    -- BAD-NAME: describe-errors.lua:[[@LINE+1]]: forge.test: the first entry must be a snake_case name, got 'Core'
    forge.test { "Core" }
elseif case == "positional" then
    -- POSITIONAL: describe-errors.lua:[[@LINE+1]]: forge.component 'core': unexpected positional entry 2
    forge.component { "core", "support" }
elseif case == "unknown-key" then
    -- UNKNOWN-KEY: describe-errors.lua:[[@LINE+1]]: forge.component 'core': unknown key 'deps'
    forge.component { "core", deps = { "support" } }
elseif case == "bad-dependency" then
    -- BAD-DEPENDENCY: describe-errors.lua:[[@LINE+1]]: forge.test 'core': dependency 'Support' is not a snake_case name
    forge.test { "core", dependencies = { "Support" } }
elseif case == "duplicate-dependency" then
    -- DUPLICATE-DEPENDENCY: describe-errors.lua:[[@LINE+1]]: forge.component 'core': dependency 'support' is listed twice
    forge.component { "core", dependencies = { "support", "support" } }
end

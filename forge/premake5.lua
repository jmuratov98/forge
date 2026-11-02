-- SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

-- forge components and their unit tests. A component builds from
-- include/forge/<name>/ and source/forge/<name>/, a test from unittests/<name>/.
-- Whether components become static libraries or one shared libforge is decided by
-- premake/forge.lua, not here.

return {
    forge.component { "core",
        dependencies = {}
    },
    forge.test { "core",
        dependencies = { "core" }
    },
}

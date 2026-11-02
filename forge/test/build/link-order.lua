-- In static mode a unit test links the closure of its dependencies, dependents before their
-- dependencies as GNU ld requires, whatever order the description lists them in. A component without
-- sources has no library and is never linked, but what it depends on is.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t --cc=clang --os=linux ninja
-- RUN: FileCheck %s --input-file=%t/forge_ir_unittests.ninja
--
-- CHECK: links_forge_ir_unittests_Debug = Debug/bin/libforge_lexer.a Debug/bin/libforge_ir.a Debug/bin/libforge_core.a Debug/bin/libforge_support.a Debug/bin/libthird_party_stub.a -lpthread{{$}}

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "support", "lexer", "core", "ir" })

forge.emit({
    forge.component { "support" },
    forge.component { "lexer" },
    forge.component { "headers_only", dependencies = { "lexer" } },
    forge.component { "core", dependencies = { "support" } },
    forge.component { "ir", dependencies = { "core" } },
    forge.test { "ir", dependencies = { "core", "ir", "headers_only" } },
}, third_party)

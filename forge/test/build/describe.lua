-- forge-describe prints, on one line of JSON, what ./x needs: the configurations, every Forge
-- option with its value name, default and allowed values (never the toolchain paths, which ./x
-- derives itself), and the component graph in declaration order. It writes nothing, not even the
-- lit site configs the generating actions get.
--
-- RUN: rm -rf %t
-- RUN: %premake --file=%s --to=%t --no-tests forge-describe | FileCheck %s --implicit-check-not=cxx-path
-- RUN: not cat %t/Debug/test/lit.site.cfg.py
--
-- CHECK: {"components":[{"dependencies":[],"name":"support"},{"dependencies":["support"],"name":"core"}]
-- CHECK-SAME: "configurations":["Debug","Release","RelDeb","Sanitize"]
-- CHECK-SAME: {"allowed":[],"description":"{{[^"]*}}","trigger":"shared"}
-- CHECK-SAME: {"allowed":["c++20","c++23"],"default":"c++20","description":"{{[^"]*}}","trigger":"std","value":"STD"}
-- CHECK-SAME: "tests":[{"dependencies":["core"],"name":"core"}]

dofile(path.join(_SCRIPT_DIR, "Inputs/fixture.lua"))

local third_party = fixture.workspace({ "core" })

forge.emit({
    forge.component { "support" },
    forge.component { "core", dependencies = { "support" } },
    forge.test { "core", dependencies = { "core" } },
}, third_party)

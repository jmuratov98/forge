// Allowlisted standard headers, Forge's own headers, and quoted includes.
#include <atomic>
#include <bit>
#include <cstdint>
#include <cstring>
#include <source_location>
#include <type_traits>
#include <forge/core/string_view.hpp>
#include "forge/c/parser.hpp"
#include "vector"
#  include   <utility>

/* #include <vector> is only a comment
#include <map>
*/
// #include <string>
const char* text = "#include <set>";
const char* raw = R"(
#include <iostream>
)";

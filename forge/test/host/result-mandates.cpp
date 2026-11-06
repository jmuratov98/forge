// The ill-formed uses of result that docs/result.md lists fail to compile, and the well-formed
// neighbours of each do not. Every compiler prints the message of a static_assert; for a returned
// argument that is neither a value nor an error, each has its own words. A format-spec fails the
// constant evaluation in format_without_spec::parse: GCC and MSVC name it in their call stacks,
// while Clang calls it `parse` but shows the failing line, which holds the message. MSVC shows no
// source lines, so it never prints the message.
//
// DEFINE: %{compile} = %host_cxx_syntax %s
// RUN: %{compile} -DCASE=0
// RUN: not %{compile} -DCASE=1 2>&1 | FileCheck %s --check-prefix=VALUE
// RUN: not %{compile} -DCASE=2 2>&1 | FileCheck %s --check-prefix=ERROR
// RUN: not %{compile} -DCASE=3 2>&1 | FileCheck %s --check-prefix=VALUE
// RUN: not %{compile} -DCASE=4 2>&1 | FileCheck %s --check-prefix=RETURN
// RUN: not %{compile} -DCASE=5 2>&1 | FileCheck %s --check-prefix=RETURN
// RUN: not %{compile} -DCASE=6 2>&1 | FileCheck %s --check-prefix=DELETED
// RUN: not %{compile} -DCASE=7 2>&1 | FileCheck %s --check-prefix=RETURN
// RUN: not %{compile} -DCASE=8 2>&1 | FileCheck %s --check-prefix=TRANSFORM
// RUN: not %{compile} -DCASE=9 2>&1 | FileCheck %s --check-prefix=FORMAT
//
// VALUE: is not a valid value type
// ERROR: is not a valid error type
// RETURN: {{no viable conversion|could not convert|cannot convert}}
// DELETED: {{deleted function}}
// TRANSFORM: cannot return a reference from an rvalue result
// FORMAT: {{format_without_spec::parse|result, success and failure take no format-spec}}

#include "forge/core/result.hpp"

#include <format>
#include <string>
#include <string_view>

using namespace forge;

#if CASE == 0
// Each of these is well-formed.
result<int, std::string_view> ok_value() { return 1; }
result<int, std::string_view> ok_error() { return "text"; }
result<bool, std::string_view> ok_explicit() { return failure("oops"); }
result<std::string, std::string_view> ok_success(std::string_view sv) {
    return success(std::string(sv));
}
result<int&, int> ok_reference(int& x) { return x; }
std::string ok_format() { return std::format("{}", result<int, int>(1)); }
#elif CASE == 1
// A value type cannot be const.
result<const int, int> r(1);
#elif CASE == 2
// An error type cannot be an array.
result<int, int[2]>* p;
failure<int[2]> f(1);
#elif CASE == 3
// Nor a tag or a wrapper.
result<success<int>, int> r(in_place, 1);
#elif CASE == 4
// Narrowing to bool while the error type accepts the argument.
result<bool, std::string_view> f() { return "oops"; }
#elif CASE == 5
// std::string has an explicit constructor from a string_view.
result<std::string, std::string_view> h(std::string_view sv) { return sv; }
#elif CASE == 6
// A temporary would bind: neither a value nor an error.
result<const int&, int> g() { return 42; }
#elif CASE == 7
// A double is narrowed to int, which the error type accepts.
result<int, double> d() { return 3.5; }
#elif CASE == 8
// A reference into a temporary would dangle.
struct holder { int member; };
auto bad(result<holder, int>&& r) {
    return std::move(r).transform([](holder&& h) -> int& { return h.member; });
}
#elif CASE == 9
// A format-spec is not accepted, also during constant evaluation of the format string.
std::string f(const result<int, int>& r) { return std::format("{:x}", r); }
#endif

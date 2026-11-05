# Results [result]

Status: draft, 2026-11-04.

## 0 Conventions [result.conventions]

1 This document follows the conventions of [stacktrace.conventions] (`docs/stacktrace.md`).
Unqualified stable names such as [expected.object.assign] refer to ISO/IEC 14882:2024. Clauses 1 to
11 are normative; Annexes A and B are informative.

2 Code in this document that names a member `m_`*name* is exposition only. Names in italics, such
as *value-implicit*, are exposition only as well.

## 1 Scope [result.scope]

1 This document specifies the class templates `result`, `success` and `failure` of forge's `core`
component. A `result<T, E>` holds either a value of type `T` or an error of type `E`. These
templates report a failure of an operation of forge itself, such as reading a file or parsing a
number, to that operation's caller.

2 The following are outside the scope of this document:

- (2.1) problems in the program being compiled, which are diagnostics, not results;
- (2.2) bugs in forge, which `FORGE_ASSERT` checks (`forge/core/assert.hpp`);
- (2.3) the error types of particular operations, which the documents for those operations
  specify;
- (2.4) macros that return early from a function when a result holds an error;
- (2.5) conversions between `result` and `std::expected`.

## 2 Terms and definitions [result.defs]

**2.1 contained value**: the object of type `T` that a `result<T, E>` holds when `has_value()` is
`true`; for `result<T&, E>`, the object that the held reference refers to.

**2.2 contained error**: the object of type `E` that a `result<T, E>` holds when `has_value()` is
`false`.

**2.3 valid value type**: `void`; a non-array object type that is not cv-qualified; or an lvalue
reference to a possibly const-qualified non-array object type. In every case the type is not
`in_place_t`, `in_place_failure_t`, or a specialization of `success` or `failure`, and its
referenced type, if any, is not either of them.

**2.4 valid error type**: a non-array object type that is not cv-qualified and that is not
`in_place_t`, `in_place_failure_t`, or a specialization of `success`, `failure` or `result`.

## 3 Header `<forge/core/result.hpp>` synopsis [result.syn]

```cpp
#include "forge/core/in_place.hpp" // in_place_t, in_place

#include <format>
#include <initializer_list>
#include <type_traits>

namespace forge {

// [result.tags], construction tags
struct in_place_failure_t {
    explicit in_place_failure_t() = default;
};
inline constexpr in_place_failure_t in_place_failure{};

// [result.success], class template success
template <typename T = void>
class success;
template <typename T>
class success<T&>;
template <>
class success<void>;

// [result.failure], class template failure
template <typename E>
class failure;

// [result.object], class template result
template <typename T, typename E>
class result;

// [result.void], partial specialization for void values
template <typename E>
class result<void, E>;

// [result.ref], partial specialization for reference values
template <typename T, typename E>
class result<T&, E>;

} // namespace forge

// [result.format], formatting
template <typename T, typename E>
struct std::formatter<forge::result<T, E>, char>;
template <typename T>
struct std::formatter<forge::success<T>, char>;
template <typename E>
struct std::formatter<forge::failure<E>, char>;
```

1 The header declares no other names in namespace `forge` other than names in `forge::detail`.

2 The header `<forge/core/in_place.hpp>` defines `in_place_t` and `in_place`:

```cpp
namespace forge {

struct in_place_t {
    explicit in_place_t() = default;
};
inline constexpr in_place_t in_place{};

} // namespace forge
```

[Note 1: `in_place` is in a header of its own because it is not specific to `result`: other
holders of one object can use it without including this one. — end note]

## 4 General requirements [result.reqs]

1 A program that instantiates `result<T, E>` or `success<T>` with a `T` that is not a valid value
type, or `result<T, E>` or `failure<E>` with an `E` that is not a valid error type, is ill-formed.

2 For types `U` and `X`, *narrowing*`<U, X>` is `true` if and only if `X` is an object type,
`std::is_convertible_v<U, X>` is `true`, and copy-list-initialization of an object of type `X` from
`{std::declval<U>()}` is ill-formed. For a type `U` and an lvalue reference type `X&`,
*binds-directly*`<U, X&>` is `true` if and only if `U` is an lvalue reference type and
`std::is_convertible_v<std::remove_reference_t<U>*, X*>` is `true`.

[Note 1: The test depends on the type of `U` only, never on a value: `int` to `std::size_t` is
narrowing even for the literal `0`, and a pointer to `bool` is narrowing since C++20 (P1957,
[dcl.init.list]). It only classifies `U`: the members of this document initialize objects with
direct-non-list-initialization, so a `T` with an initializer-list constructor is initialized as by
`T(u)`. — end note]

3 For a `result<T, E>`, *value-implicit*`<U>` is `true` if and only if:

- (3.1) `T` is an object type, `std::is_convertible_v<U, T>` is `true`, and either
  *narrowing*`<U, T>` is `false` or `std::is_convertible_v<U, E>` is `false`; or
- (3.2) `T` is a reference type and *binds-directly*`<U, T>` is `true`.

For `result<void, E>`, *value-implicit*`<U>` is `false`.

4 For a `result<T, E>`, *error-implicit*`<G>` is `true` if and only if `std::is_convertible_v<G, E>`
is `true` and, unless `T` is `void`, `std::is_constructible_v<T, G>` is `false`.

[Note 2: An argument that `T` can be constructed from in any way never becomes the error
implicitly, and an argument that converts to `T` only by narrowing while `E` would accept it
becomes neither. Each needs `success(...)` or `failure(...)`. So at most one of the two holds for
any `U`, and `return` never decides between value and error by a narrowing conversion.
*binds-directly* allows only bindings that need neither a temporary nor a user-defined
conversion. — end note]

5 Each *Preconditions* element of this document is checked by `FORGE_ASSERT`
(`forge/core/assert.hpp`) before the function's effects. With `FORGE_ASSERTIONS_ENABLED` 1, a
violation writes the failure report and ends the program; with it 0, the condition is not
evaluated and a violation is undefined behavior. In every configuration, a violation during
constant evaluation makes the evaluation not a constant expression. The message of the report is
unspecified.

6 Every member and friend function, and every constructor and destructor, specified in this
document is `constexpr`. A function declared `noexcept` or `noexcept(`*expr*`)` in this document
has that exception specification; every other one propagates any exception that the operations of
`T`, `E` or a given function object throw, and no other. None of them allocates storage beyond what
those operations allocate.

7 Each class template, partial specialization and explicit specialization of this document is
declared `[[nodiscard]]` on its definition.

[Note 3: The attribute of a primary template does not apply to its specializations, and on a
declaration of a specialization that is not a definition GCC ignores it with a warning.
— end note]

8 A `result<T, E>` for a non-void object type `T` stores its contained value or its contained error
in a member union and records which of the two it holds in a `bool`; `result<void, E>` and
`result<T&, E>` do the same with `E` and, for `T&`, a pointer to `T`.

[Note 4: A discarded call that returns one of these classes is a warning ([dcl.attr.nodiscard]),
which `--werror` makes an error. Clang also warns for a discarded temporary such as
`forge::success{x};`; GCC does not. forge has no run-time check that a result was inspected
([result.rationale.llvm]). — end note]

## 5 Construction tags [result.tags]

1 `in_place_t` and `in_place_failure_t` are empty class types. Their default constructors are
explicit, so that `{}` does not convert to them. `in_place` selects a constructor that initializes
the contained value from its arguments; `in_place_failure` one that initializes the contained error.

[Note 1: forge defines its own `in_place_t` rather than using `std::in_place_t`, so that both tags
of a `result` are forge's and have names that say which state they select. — end note]

## 6 Class template `success` [result.success]

```cpp
namespace forge {

template <typename T>
class [[nodiscard]] success {
public:
    constexpr success(const success&) = default;
    constexpr success(success&&) = default;
    template <typename U = T>
    constexpr explicit success(U&& v);
    template <typename... Args>
    constexpr explicit success(in_place_t, Args&&... args);
    template <typename U, typename... Args>
    constexpr explicit success(in_place_t, std::initializer_list<U> list, Args&&... args);

    constexpr success& operator=(const success&) = default;
    constexpr success& operator=(success&&) = default;

    [[nodiscard]] constexpr const T& value() const& noexcept;
    [[nodiscard]] constexpr T& value() & noexcept;
    [[nodiscard]] constexpr const T&& value() const&& noexcept;
    [[nodiscard]] constexpr T&& value() && noexcept;

    constexpr void swap(success& other) noexcept(std::is_nothrow_swappable_v<T>);
    friend constexpr void swap(success& x, success& y) noexcept(noexcept(x.swap(y)));

    template <typename T2>
    friend constexpr bool operator==(const success& x, const success<T2>& y);

private:
    T m_value; // exposition only
};

template <typename T>
class [[nodiscard]] success<T&> {
public:
    template <typename U>
    constexpr explicit success(U&& v) noexcept;

    [[nodiscard]] constexpr T& value() const noexcept;

    template <typename T2>
    friend constexpr bool operator==(const success& x, const success<T2>& y);

private:
    T* m_value; // exposition only
};

template <>
class [[nodiscard]] success<void> {
public:
    constexpr success() noexcept = default;

    friend constexpr bool operator==(success, success) noexcept;
};

template <typename T>
success(T) -> success<T>;
success() -> success<void>;

} // namespace forge
```

1 A `success<T>` holds a value that is to become the contained value of a `result`. The deduction
guides make `success(v)` hold a copy of `v` (with arrays and functions decayed), and `success()` a
`success<void>`; a `success<T&>` is named only explicitly.

```cpp
template <typename U = T>
constexpr explicit success(U&& v);
```

2 *Constraints*: `std::remove_cvref_t<U>` is neither `success` nor `in_place_t`, and
`std::is_constructible_v<T, U>` is `true`.

3 *Effects*: Direct-non-list-initializes `m_value` with `std::forward<U>(v)`.

4 *Throws*: Any exception thrown by the initialization of `m_value`.

```cpp
template <typename... Args>
constexpr explicit success(in_place_t, Args&&... args);
template <typename U, typename... Args>
constexpr explicit success(in_place_t, std::initializer_list<U> list, Args&&... args);
```

5 *Constraints*: `std::is_constructible_v<T, Args...>` is `true` for the first form, and
`std::is_constructible_v<T, std::initializer_list<U>&, Args...>` for the second.

6 *Effects*: Direct-non-list-initializes `m_value` with `std::forward<Args>(args)...`, preceded by
`list` in the second form.

7 *Throws*: Any exception thrown by the initialization of `m_value`.

```cpp
constexpr const T& value() const& noexcept;
constexpr T& value() & noexcept;
constexpr const T&& value() const&& noexcept;
constexpr T&& value() && noexcept;
```

8 *Returns*: `m_value` for the first two forms, `std::move(m_value)` for the others.

```cpp
constexpr void swap(success& other) noexcept(std::is_nothrow_swappable_v<T>);
friend constexpr void swap(success& x, success& y) noexcept(noexcept(x.swap(y)));
```

9 *Constraints*: `std::is_swappable_v<T>` is `true`.

10 *Effects*: The member swaps `m_value` with `other.m_value` as if by `using std::swap;
swap(m_value, other.m_value);`. The friend is equivalent to `x.swap(y)`.

```cpp
template <typename T2>
friend constexpr bool operator==(const success& x, const success<T2>& y);
```

11 *Mandates*: `x.value() == y.value()` is well-formed and its result is convertible to `bool`.

12 *Returns*: `x.value() == y.value()`.

```cpp
template <typename U>
constexpr explicit success(U&& v) noexcept; // success<T&>
```

13 *Constraints*: *binds-directly*`<U, T&>` is `true`.

14 *Effects*: Initializes `m_value` with `std::addressof(v)`.

15 *Remarks*: `success<T&>` is trivially copyable, and its copy assignment rebinds `m_value`. Its
`value()` returns `*m_value`; its `operator==` returns `x.value() == y.value()`.

```cpp
friend constexpr bool operator==(success, success) noexcept; // success<void>
```

16 *Returns*: `true`.

## 7 Class template `failure` [result.failure]

```cpp
namespace forge {

template <typename E>
class [[nodiscard]] failure {
public:
    constexpr failure(const failure&) = default;
    constexpr failure(failure&&) = default;
    template <typename G = E>
    constexpr explicit failure(G&& e);
    template <typename... Args>
    constexpr explicit failure(in_place_t, Args&&... args);
    template <typename U, typename... Args>
    constexpr explicit failure(in_place_t, std::initializer_list<U> list, Args&&... args);

    constexpr failure& operator=(const failure&) = default;
    constexpr failure& operator=(failure&&) = default;

    [[nodiscard]] constexpr const E& error() const& noexcept;
    [[nodiscard]] constexpr E& error() & noexcept;
    [[nodiscard]] constexpr const E&& error() const&& noexcept;
    [[nodiscard]] constexpr E&& error() && noexcept;

    constexpr void swap(failure& other) noexcept(std::is_nothrow_swappable_v<E>);
    friend constexpr void swap(failure& x, failure& y) noexcept(noexcept(x.swap(y)));

    template <typename E2>
    friend constexpr bool operator==(const failure& x, const failure<E2>& y);

private:
    E m_error; // exposition only
};

template <typename E>
failure(E) -> failure<E>;

} // namespace forge
```

1 A `failure<E>` holds an error that is to become the contained error of a `result`. Its members
are specified as those of `success<T>` ([result.success]) with `T` replaced by `E`, `value` by
`error`, `m_value` by `m_error` and `success` by `failure`.

## 8 Class template `result` [result.object]

### 8.1 General [result.object.general]

```cpp
namespace forge {

template <typename T, typename E>
class [[nodiscard]] result {
public:
    using value_type = T;
    using error_type = E;
    template <typename U>
    using rebind = result<U, error_type>;

    // [result.object.ctor], constructors
    constexpr result(const result& other);
    constexpr result(result&& other) noexcept(see below);
    template <typename U>
    constexpr explicit(see below) result(U&& v);
    template <typename G>
    constexpr result(G&& e);
    template <typename U, typename G>
    constexpr explicit(see below) result(const result<U, G>& other);
    template <typename U, typename G>
    constexpr explicit(see below) result(result<U, G>&& other);
    template <typename U>
    constexpr explicit(see below) result(const success<U>& s);
    template <typename U>
    constexpr explicit(see below) result(success<U>&& s);
    template <typename G>
    constexpr explicit(see below) result(const failure<G>& f);
    template <typename G>
    constexpr explicit(see below) result(failure<G>&& f);
    template <typename... Args>
    constexpr explicit result(in_place_t, Args&&... args);
    template <typename U, typename... Args>
    constexpr explicit result(in_place_t, std::initializer_list<U> list, Args&&... args);
    template <typename... Args>
    constexpr explicit result(in_place_failure_t, Args&&... args);
    template <typename U, typename... Args>
    constexpr explicit result(in_place_failure_t, std::initializer_list<U> list, Args&&... args);

    constexpr ~result();

    // [result.object.assign], assignment
    constexpr result& operator=(const result& other);
    constexpr result& operator=(result&& other) noexcept(see below);
    template <typename U>
    constexpr result& operator=(U&& v);
    template <typename G>
    constexpr result& operator=(G&& e);
    template <typename U>
    constexpr result& operator=(const success<U>& s);
    template <typename U>
    constexpr result& operator=(success<U>&& s);
    template <typename G>
    constexpr result& operator=(const failure<G>& f);
    template <typename G>
    constexpr result& operator=(failure<G>&& f);
    template <typename... Args>
    constexpr T& emplace(Args&&... args) noexcept;
    template <typename U, typename... Args>
    constexpr T& emplace(std::initializer_list<U> list, Args&&... args) noexcept;

    // [result.object.swap], swap
    constexpr void swap(result& other) noexcept(see below);
    friend constexpr void swap(result& x, result& y) noexcept(noexcept(x.swap(y)));

    // [result.object.obs], observers
    [[nodiscard]] constexpr const T* operator->() const noexcept;
    [[nodiscard]] constexpr T* operator->() noexcept;
    [[nodiscard]] constexpr const T& operator*() const& noexcept;
    [[nodiscard]] constexpr T& operator*() & noexcept;
    [[nodiscard]] constexpr const T&& operator*() const&& noexcept;
    [[nodiscard]] constexpr T&& operator*() && noexcept;
    [[nodiscard]] constexpr explicit operator bool() const noexcept;
    [[nodiscard]] constexpr bool has_value() const noexcept;
    [[nodiscard]] constexpr const T& value() const& noexcept;
    [[nodiscard]] constexpr T& value() & noexcept;
    [[nodiscard]] constexpr const T&& value() const&& noexcept;
    [[nodiscard]] constexpr T&& value() && noexcept;
    [[nodiscard]] constexpr const E& error() const& noexcept;
    [[nodiscard]] constexpr E& error() & noexcept;
    [[nodiscard]] constexpr const E&& error() const&& noexcept;
    [[nodiscard]] constexpr E&& error() && noexcept;
    template <typename U>
    [[nodiscard]] constexpr T value_or(U&& fallback) const&;
    template <typename U>
    [[nodiscard]] constexpr T value_or(U&& fallback) &&;
    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) const&;
    template <typename G>
    [[nodiscard]] constexpr E error_or(G&& fallback) &&;

    // [result.object.monadic], monadic operations
    template <typename F> constexpr auto and_then(F&& f) &;
    template <typename F> constexpr auto and_then(F&& f) &&;
    template <typename F> constexpr auto and_then(F&& f) const&;
    template <typename F> constexpr auto and_then(F&& f) const&&;
    template <typename F> constexpr auto or_else(F&& f) &;
    template <typename F> constexpr auto or_else(F&& f) &&;
    template <typename F> constexpr auto or_else(F&& f) const&;
    template <typename F> constexpr auto or_else(F&& f) const&&;
    template <typename F> constexpr auto transform(F&& f) &;
    template <typename F> constexpr auto transform(F&& f) &&;
    template <typename F> constexpr auto transform(F&& f) const&;
    template <typename F> constexpr auto transform(F&& f) const&&;
    template <typename F> constexpr auto transform_error(F&& f) &;
    template <typename F> constexpr auto transform_error(F&& f) &&;
    template <typename F> constexpr auto transform_error(F&& f) const&;
    template <typename F> constexpr auto transform_error(F&& f) const&&;

    // [result.object.eq], equality operators
    template <typename T2, typename E2>
        requires(!std::is_void_v<T2>)
    friend constexpr bool operator==(const result& x, const result<T2, E2>& y);
    template <typename T2>
    friend constexpr bool operator==(const result& x, const T2& v);
    template <typename T2>
    friend constexpr bool operator==(const result& x, const success<T2>& s);
    template <typename E2>
    friend constexpr bool operator==(const result& x, const failure<E2>& f);

private:
    bool m_has_value; // exposition only
    union {
        T m_value; // exposition only
        E m_error; // exposition only
    };
};

} // namespace forge
```

1 This clause specifies `result<T, E>` for an object type `T`. [result.void] and [result.ref]
specify the partial specializations for `void` and for lvalue references by their differences from
this clause.

2 `result` has no default constructor.

[Note 1: `std::expected` value-initializes `T`. A `result` whose value nobody chose would make a
failure path that forgot to set an error look like a success; `return {};` is therefore ill-formed
for a non-void `T`. — end note]

[Example 1:
```cpp
forge::result<int, std::string_view> parse_count(int x) noexcept {
    if (x < 0) {
        return "count cannot be negative"; // failure: int cannot be made from it
    }
    return x;                              // success
}

forge::result<std::size_t, std::errc> size() {
    return 0;                              // success: narrowing, but std::errc rejects it
}

forge::result<std::string_view, std::string_view> g() {
    return "text";                         // success: converts to both, the value wins
    return forge::failure("text");         // failure must be explicit
}

forge::result<bool, std::string_view> f() {
    return "oops";                         // ill-formed: narrowing to bool, and E accepts it
    return forge::failure("oops");         // OK
}

forge::result<std::string, std::string_view> h(std::string_view sv) {
    return sv;                             // ill-formed: std::string has an explicit constructor
    return forge::success(std::string(sv)); // OK
}
```
— end example]

### 8.2 Constructors [result.object.ctor]

```cpp
constexpr result(const result& other);
```

1 *Effects*: If `other.has_value()`, direct-non-list-initializes the contained value with
`*other`; otherwise, the contained error with `other.error()`.

2 *Postconditions*: `has_value() == other.has_value()`.

3 *Throws*: Any exception thrown by the initialization.

4 *Remarks*: This constructor is defined as deleted unless `std::is_copy_constructible_v<T>` and
`std::is_copy_constructible_v<E>` are both `true`. It is trivial if
`std::is_trivially_copy_constructible_v<T>` and `std::is_trivially_copy_constructible_v<E>` are both
`true`.

```cpp
constexpr result(result&& other) noexcept(see below);
```

5 *Constraints*: `std::is_move_constructible_v<T>` and `std::is_move_constructible_v<E>` are both
`true`.

6 *Effects*: As paragraph 1, with `std::move(*other)` and `std::move(other.error())`.

7 *Postconditions*: `has_value() == other.has_value()`. The state of `other`'s contained value or
error is that of a moved-from object of its type.

8 *Throws*: Any exception thrown by the initialization.

9 *Remarks*: The expression inside `noexcept` is `std::is_nothrow_move_constructible_v<T> &&
std::is_nothrow_move_constructible_v<E>`. The constructor is trivial if
`std::is_trivially_move_constructible_v<T>` and `std::is_trivially_move_constructible_v<E>` are both
`true`.

```cpp
template <typename U>
constexpr explicit(see below) result(U&& v);
```

10 *Constraints*:

- (10.1) `std::remove_cvref_t<U>` is not `in_place_t`, `in_place_failure_t`, `result`, or a
  specialization of `success` or `failure`;
- (10.2) if `T` is `bool`, `std::remove_cvref_t<U>` is not a specialization of `result`; and
- (10.3) `std::is_constructible_v<T, U>` is `true`.

11 *Effects*: Direct-non-list-initializes the contained value with `std::forward<U>(v)`.

12 *Postconditions*: `has_value()` is `true`.

13 *Throws*: Any exception thrown by the initialization.

14 *Remarks*: The expression inside `explicit` is `!`*value-implicit*`<U>`.

[Note 1: Items (10.1) and (10.2) are those of `std::expected`, so that a `result<result<int, E>, E>`
can be made from a `result<int, E>`. In direct-initialization the value wins:
`forge::result<int, double>(3.5)` holds the value `3`, while `return 3.5;` from a function that
returns `result<int, double>` is ill-formed. — end note]

```cpp
template <typename G>
constexpr result(G&& e);
```

15 *Constraints*: `std::remove_cvref_t<G>` is not `in_place_t`, `in_place_failure_t`, or a
specialization of `result`, `success` or `failure`, and *error-implicit*`<G>` is `true`.

16 *Effects*: Direct-non-list-initializes the contained error with `std::forward<G>(e)`.

17 *Postconditions*: `has_value()` is `false`.

18 *Throws*: Any exception thrown by the initialization.

[Note 2: *error-implicit* requires that `T` cannot be constructed from `G`, and paragraph 10 that
it can, so no argument selects both constructors. There is no explicit form: any other error is
written `failure(e)` or `result(in_place_failure, e)`. — end note]

```cpp
template <typename U, typename G>
constexpr explicit(see below) result(const result<U, G>& other);
template <typename U, typename G>
constexpr explicit(see below) result(result<U, G>&& other);
```

19 Let `GF` be `const G&` for the first form and `G` for the second. Let `UF` be `U&` if `U` is a
reference type, and otherwise `const U&` for the first form and `U` for the second. Let `W` be
`result<U, G>`.

20 *Constraints*:

- (20.1) `U` is not `void`;
- (20.2) `std::is_constructible_v<T, UF>` and `std::is_constructible_v<E, GF>` are both `true`;
- (20.3) if `T` is not `bool`, *converts-from-any-cvref*`<T, W>` ([expected.object.cons]) is
  `false`; and
- (20.4) `std::is_constructible_v<failure<E>, X>` is `false` for each `X` of `W&`, `W`, `const W&`
  and `const W`.

21 *Effects*: If `other.has_value()`, direct-non-list-initializes the contained value with
`std::forward<UF>(*other)`; otherwise, the contained error with `std::forward<GF>(other.error())`.

22 *Postconditions*: `has_value() == other.has_value()`.

23 *Throws*: Any exception thrown by the initialization.

24 *Remarks*: The expression inside `explicit` is `std::is_reference_v<U> ||
!std::is_convertible_v<UF, T> || !std::is_convertible_v<GF, E>`.

[Note 3: The state of `other` is known, so no narrowing rule applies. A `result<U&, G>` converts by
copying the referent, and only explicitly, so that no copy goes unnoticed. — end note]

```cpp
template <typename U>
constexpr explicit(see below) result(const success<U>& s);
template <typename U>
constexpr explicit(see below) result(success<U>&& s);
```

25 Let `UF` be `U&` if `U` is a reference type, and otherwise `const U&` for the first form and
`U` for the second.

26 *Constraints*: `U` is not `void` and `std::is_constructible_v<T, UF>` is `true`.

27 *Effects*: Direct-non-list-initializes the contained value with `std::forward<UF>(s.value())`.

28 *Postconditions*: `has_value()` is `true`.

29 *Throws*: Any exception thrown by the initialization.

30 *Remarks*: The expression inside `explicit` is `std::is_reference_v<U> ||
!std::is_convertible_v<UF, T>`.

```cpp
template <typename G>
constexpr explicit(see below) result(const failure<G>& f);
template <typename G>
constexpr explicit(see below) result(failure<G>&& f);
```

31 Let `GF` be `const G&` for the first form and `G` for the second.

32 *Constraints*: `std::is_constructible_v<E, GF>` is `true`.

33 *Effects*: Direct-non-list-initializes the contained error with `std::forward<GF>(f.error())`.

34 *Postconditions*: `has_value()` is `false`.

35 *Throws*: Any exception thrown by the initialization.

36 *Remarks*: The expression inside `explicit` is `!std::is_convertible_v<GF, E>`.

```cpp
template <typename... Args>
constexpr explicit result(in_place_t, Args&&... args);
template <typename U, typename... Args>
constexpr explicit result(in_place_t, std::initializer_list<U> list, Args&&... args);
template <typename... Args>
constexpr explicit result(in_place_failure_t, Args&&... args);
template <typename U, typename... Args>
constexpr explicit result(in_place_failure_t, std::initializer_list<U> list, Args&&... args);
```

37 *Constraints*: For the `in_place_t` forms, `std::is_constructible_v<T, Args...>`, respectively
`std::is_constructible_v<T, std::initializer_list<U>&, Args...>`, is `true`; for the
`in_place_failure_t` forms, the same with `E`.

38 *Effects*: Direct-non-list-initializes the contained value (`in_place_t`), respectively the
contained error (`in_place_failure_t`), with `std::forward<Args>(args)...`, preceded by `list` in
the `std::initializer_list` forms.

39 *Postconditions*: `has_value()` is `true` for the `in_place_t` forms and `false` otherwise.

40 *Throws*: Any exception thrown by the initialization.

```cpp
constexpr ~result();
```

41 *Effects*: Destroys the contained value or the contained error.

42 *Remarks*: The destructor is trivial if `std::is_trivially_destructible_v<T>` and
`std::is_trivially_destructible_v<E>` are both `true`. If, in addition, the copy and move
constructors and assignment operators are trivial or deleted, and at least one of them is not
deleted, `result<T, E>` is trivially copyable.

[Note 4: The triviality follows from conditionally trivial special members ([class.dtor],
[special]; P0848): each special member has a defaulted overload constrained on the triviality of
`T` and `E`, next to the user-provided one. The implementation therefore needs no hierarchy of
storage base classes ([result.rationale.prior] paragraph 2). — end note]

### 8.3 Assignment [result.object.assign]

1 In this subclause, *reinit*`(newval, oldval, args...)` ends the lifetime of `oldval` and
creates `newval` from `args...`. If `FORGE_EXCEPTIONS_ENABLED` is 1, it is the exposition-only
function *reinit-expected* of [expected.object.assign], which restores `oldval` and propagates the
exception if creating `newval` throws. If it is 0, *reinit* destroys `oldval` and then
direct-non-list-initializes `newval`, with no temporary.

2 *may-reinit* is `true` if `FORGE_EXCEPTIONS_ENABLED` is 0, and otherwise
`std::is_nothrow_move_constructible_v<T> || std::is_nothrow_move_constructible_v<E>`.

[Note 1: Without exceptions nothing can throw, so a type whose move constructor is not marked
`noexcept` keeps its assignment. With them, the condition is that of `std::expected`: one of the
two must move without throwing, so that the old state can be restored. — end note]

```cpp
constexpr result& operator=(const result& other);
```

3 *Effects*:

- (3.1) If `this->has_value()` and `other.has_value()`, equivalent to `m_value = *other`.
- (3.2) Otherwise, if `this->has_value()`, equivalent to
  *reinit*`(m_error, m_value, other.error())`.
- (3.3) Otherwise, if `other.has_value()`, equivalent to *reinit*`(m_value, m_error, *other)`.
- (3.4) Otherwise, equivalent to `m_error = other.error()`.

Then, if no exception was thrown, `m_has_value` is `other.has_value()`.

4 *Returns*: `*this`.

5 *Remarks*: This operator is defined as deleted unless `std::is_copy_assignable_v<T>`,
`std::is_copy_constructible_v<T>`, `std::is_copy_assignable_v<E>` and
`std::is_copy_constructible_v<E>` are all `true`, and *may-reinit* is `true`. It is trivial if
the copy constructor and destructor of `result` are trivial and
`std::is_trivially_copy_assignable_v<T>` and `std::is_trivially_copy_assignable_v<E>` are both
`true`.

```cpp
constexpr result& operator=(result&& other) noexcept(see below);
```

6 *Constraints*: `std::is_move_constructible_v<T>`, `std::is_move_assignable_v<T>`,
`std::is_move_constructible_v<E>` and `std::is_move_assignable_v<E>` are all `true`, and
*may-reinit* is `true`.

7 *Effects*: As paragraph 3, with `std::move(*other)` and `std::move(other.error())`.

8 *Returns*: `*this`.

9 *Remarks*: The expression inside `noexcept` is `std::is_nothrow_move_assignable_v<T> &&
std::is_nothrow_move_constructible_v<T> && std::is_nothrow_move_assignable_v<E> &&
std::is_nothrow_move_constructible_v<E>`. The operator is trivial under the conditions of
paragraph 5 with "copy" read as "move".

```cpp
template <typename U>
constexpr result& operator=(U&& v);
```

10 *Constraints*: The constraints of [result.object.ctor] paragraph 10 hold;
*value-implicit*`<U>` and `std::is_assignable_v<T&, U>` are both `true`; and
`std::is_nothrow_constructible_v<T, U>` or *may-reinit* is `true`.

11 *Effects*: If `has_value()`, equivalent to `m_value = std::forward<U>(v)`; otherwise, to
*reinit*`(m_value, m_error, std::forward<U>(v))` and then `m_has_value = true`.

12 *Returns*: `*this`.

[Note 2: Assignment chooses between value and error by the rule of `return`: `r = 3.5` assigns
the value `3` to a `result<int, std::errc>` and is ill-formed for a `result<int, double>`.
— end note]

```cpp
template <typename G>
constexpr result& operator=(G&& e);
```

13 *Constraints*: The constraints of [result.object.ctor] paragraph 15 hold;
`std::is_assignable_v<E&, G>` is `true`; and `std::is_nothrow_constructible_v<E, G>` or
*may-reinit* is `true`.

14 *Effects*: If `!has_value()`, equivalent to `m_error = std::forward<G>(e)`; otherwise, to
*reinit*`(m_error, m_value, std::forward<G>(e))` and then `m_has_value = false`.

15 *Returns*: `*this`.

```cpp
template <typename U>
constexpr result& operator=(const success<U>& s);
template <typename U>
constexpr result& operator=(success<U>&& s);
template <typename G>
constexpr result& operator=(const failure<G>& f);
template <typename G>
constexpr result& operator=(failure<G>&& f);
```

16 Let `UF` and `GF` be as for the corresponding constructors ([result.object.ctor] paragraphs 25
and 31).

17 *Constraints*: For the `success` forms: `U` is not `void`; `std::is_constructible_v<T, UF>` and
`std::is_assignable_v<T&, UF>` are both `true`; and `std::is_nothrow_constructible_v<T, UF>` or
*may-reinit* is `true`. For the `failure` forms: `std::is_constructible_v<E, GF>` and
`std::is_assignable_v<E&, GF>` are both `true`, and `std::is_nothrow_constructible_v<E, GF>` or
*may-reinit* is `true`.

18 *Effects*: As paragraph 11 with `std::forward<UF>(s.value())`, respectively paragraph 14 with
`std::forward<GF>(f.error())`.

19 *Returns*: `*this`.

```cpp
template <typename... Args>
constexpr T& emplace(Args&&... args) noexcept;
template <typename U, typename... Args>
constexpr T& emplace(std::initializer_list<U> list, Args&&... args) noexcept;
```

20 *Constraints*: `std::is_constructible_v<T, Args...>`, respectively
`std::is_constructible_v<T, std::initializer_list<U>&, Args...>`, is `true`, and, if
`FORGE_EXCEPTIONS_ENABLED` is 1, so is the corresponding `std::is_nothrow_constructible_v`.

21 *Effects*: Destroys the contained value or error, then direct-non-list-initializes the contained
value with `std::forward<Args>(args)...`, preceded by `list` in the second form.

22 *Postconditions*: `has_value()` is `true`.

23 *Returns*: A reference to the contained value.

### 8.4 Swap [result.object.swap]

```cpp
constexpr void swap(result& other) noexcept(see below);
friend constexpr void swap(result& x, result& y) noexcept(noexcept(x.swap(y)));
```

1 *Constraints*: `std::is_swappable_v<T>`, `std::is_swappable_v<E>`,
`std::is_move_constructible_v<T>` and `std::is_move_constructible_v<E>` are all `true`, and
*may-reinit* ([result.object.assign] paragraph 2) is `true`.

2 *Effects*: The member is equivalent to the member `swap` of `std::expected`
([expected.object.swap]); a swap between a result with a value and one with an error leaves both
unchanged if it throws. The friend is equivalent to `x.swap(y)`.

3 *Remarks*: The expression inside the member's `noexcept` is
`std::is_nothrow_move_constructible_v<T> && std::is_nothrow_swappable_v<T> &&
std::is_nothrow_move_constructible_v<E> && std::is_nothrow_swappable_v<E>`.

### 8.5 Observers [result.object.obs]

```cpp
constexpr const T* operator->() const noexcept;
constexpr T* operator->() noexcept;
```

1 *Preconditions*: `has_value()` is `true`.

2 *Returns*: `std::addressof(m_value)`.

```cpp
constexpr const T& operator*() const& noexcept;
constexpr T& operator*() & noexcept;
constexpr const T&& operator*() const&& noexcept;
constexpr T&& operator*() && noexcept;
constexpr const T& value() const& noexcept;
constexpr T& value() & noexcept;
constexpr const T&& value() const&& noexcept;
constexpr T&& value() && noexcept;
```

3 *Preconditions*: `has_value()` is `true`.

4 *Returns*: `m_value` for the lvalue forms, `std::move(m_value)` for the rvalue forms.

[Note 1: `value()` and `operator*` behave the same. `std::expected::value()` throws
`bad_expected_access` instead, which under `-fno-exceptions` ends the program without forge's
failure report. — end note]

```cpp
constexpr explicit operator bool() const noexcept;
constexpr bool has_value() const noexcept;
```

5 *Returns*: `m_has_value`.

```cpp
constexpr const E& error() const& noexcept;
constexpr E& error() & noexcept;
constexpr const E&& error() const&& noexcept;
constexpr E&& error() && noexcept;
```

6 *Preconditions*: `has_value()` is `false`.

7 *Returns*: `m_error` for the lvalue forms, `std::move(m_error)` for the rvalue forms.

```cpp
template <typename U>
constexpr T value_or(U&& fallback) const&;
template <typename U>
constexpr T value_or(U&& fallback) &&;
```

8 *Mandates*: `std::is_convertible_v<U, T>` is `true`, and `std::is_copy_constructible_v<T>`,
respectively `std::is_move_constructible_v<T>`, is `true`.

9 *Returns*: `has_value() ? **this : static_cast<T>(std::forward<U>(fallback))` for the first form,
and the same with `std::move(**this)` for the second.

```cpp
template <typename G>
constexpr E error_or(G&& fallback) const&;
template <typename G>
constexpr E error_or(G&& fallback) &&;
```

10 *Mandates*: `std::is_convertible_v<G, E>` is `true`, and `std::is_copy_constructible_v<E>`,
respectively `std::is_move_constructible_v<E>`, is `true`.

11 *Returns*: `has_value() ? static_cast<E>(std::forward<G>(fallback)) : error()` for the first
form, and the same with `std::move(error())` for the second.

### 8.6 Monadic operations [result.object.monadic]

1 In this subclause, for the overloads qualified `&` and `const&`, *VAL* is `**this` and *ERR* is
`error()`; for those qualified `&&` and `const&&`, *VAL* is `std::move(**this)` and *ERR* is
`std::move(error())`.

```cpp
template <typename F> constexpr auto and_then(F&& f) &;
template <typename F> constexpr auto and_then(F&& f) &&;
template <typename F> constexpr auto and_then(F&& f) const&;
template <typename F> constexpr auto and_then(F&& f) const&&;
```

2 Let `U` be `std::remove_cvref_t<std::invoke_result_t<F, decltype(`*VAL*`)>>`.

3 *Constraints*: `std::is_constructible_v<E, decltype(`*ERR*`)>` is `true`.

4 *Mandates*: `U` is a specialization of `result` and `std::is_same_v<typename U::error_type, E>`
is `true`.

5 *Effects*: Equivalent to:
```cpp
if (has_value()) {
    return std::invoke(std::forward<F>(f), VAL);
}
return U(in_place_failure, ERR);
```

```cpp
template <typename F> constexpr auto or_else(F&& f) &;
template <typename F> constexpr auto or_else(F&& f) &&;
template <typename F> constexpr auto or_else(F&& f) const&;
template <typename F> constexpr auto or_else(F&& f) const&&;
```

6 Let `G` be `std::remove_cvref_t<std::invoke_result_t<F, decltype(`*ERR*`)>>`.

7 *Constraints*: `std::is_constructible_v<T, decltype(`*VAL*`)>` is `true`.

8 *Mandates*: `G` is a specialization of `result` and `std::is_same_v<typename G::value_type, T>`
is `true`.

9 *Effects*: Equivalent to:
```cpp
if (has_value()) {
    return G(in_place, VAL);
}
return std::invoke(std::forward<F>(f), ERR);
```

```cpp
template <typename F> constexpr auto transform(F&& f) &;
template <typename F> constexpr auto transform(F&& f) &&;
template <typename F> constexpr auto transform(F&& f) const&;
template <typename F> constexpr auto transform(F&& f) const&&;
```

10 Let `U` be `std::remove_cv_t<std::invoke_result_t<F, decltype(`*VAL*`)>>`.

11 *Constraints*: `std::is_constructible_v<E, decltype(`*ERR*`)>` is `true`.

12 *Mandates*: `U` is a valid value type, and for the overloads qualified `&&` and `const&&` it is
not a reference type.

13 *Effects*:

- (13.1) If `has_value()` is `false`, returns `result<U, E>(in_place_failure, `*ERR*`)`.
- (13.2) Otherwise, if `U` is `void`, evaluates `std::invoke(std::forward<F>(f), `*VAL*`)` and
  returns `result<void, E>()`.
- (13.3) Otherwise, returns a `result<U, E>` whose contained value is direct-non-list-initialized
  with `std::invoke(std::forward<F>(f), `*VAL*`)`.

[Note 1: Since an lvalue reference is a valid value type, an `f` that returns `X&` from an lvalue
result gives a `result<X&, E>` referring to the object that `f` returned. From an rvalue result
that object is likely part of the temporary, so the reference would dangle; there it is
ill-formed. An `f` that returns `X&&`, such as a pointer to data member applied to an rvalue, is
ill-formed in every overload, since an rvalue reference is not a valid value type. — end note]

```cpp
template <typename F> constexpr auto transform_error(F&& f) &;
template <typename F> constexpr auto transform_error(F&& f) &&;
template <typename F> constexpr auto transform_error(F&& f) const&;
template <typename F> constexpr auto transform_error(F&& f) const&&;
```

14 Let `G` be `std::remove_cv_t<std::invoke_result_t<F, decltype(`*ERR*`)>>`.

15 *Constraints*: `std::is_constructible_v<T, decltype(`*VAL*`)>` is `true`.

16 *Mandates*: `G` is a valid error type.

17 *Effects*: If `has_value()`, returns `result<T, G>(in_place, `*VAL*`)`; otherwise, a
`result<T, G>` whose contained error is direct-non-list-initialized with
`std::invoke(std::forward<F>(f), `*ERR*`)`.

### 8.7 Equality operators [result.object.eq]

```cpp
template <typename T2, typename E2>
    requires(!std::is_void_v<T2>)
friend constexpr bool operator==(const result& x, const result<T2, E2>& y);
```

1 *Constraints*: `*x == *y` and `x.error() == y.error()` are well-formed and their results are
convertible to `bool`.

2 *Returns*: If `x.has_value() != y.has_value()`, `false`; otherwise, if `x.has_value()`,
`*x == *y`; otherwise, `x.error() == y.error()`.

```cpp
template <typename T2>
friend constexpr bool operator==(const result& x, const T2& v);
```

3 *Constraints*: `T2` is not a specialization of `result`, `success` or `failure`, and `*x == v` is
well-formed and its result is convertible to `bool`.

4 *Returns*: `x.has_value() && static_cast<bool>(*x == v)`.

```cpp
template <typename T2>
friend constexpr bool operator==(const result& x, const success<T2>& s);
template <typename E2>
friend constexpr bool operator==(const result& x, const failure<E2>& f);
```

5 *Constraints*: `*x == s.value()`, respectively `x.error() == f.error()`, is well-formed and its
result is convertible to `bool`.

6 *Returns*: `x.has_value() && static_cast<bool>(*x == s.value())`, respectively
`!x.has_value() && static_cast<bool>(x.error() == f.error())`.

[Note 1: Because the argument of the second form is deduced, `r == "oops"` does not convert
`"oops"` to an error; it is ill-formed unless `T` compares with `const char*`. A comparison with an
error is written `r == forge::failure("oops")`. — end note]

## 9 Partial specialization for `void` values [result.void]

1 `result<void, E>` is specified by [result.object] with the following differences.

- (1.1) It has no contained value, `T` is `void` in `value_type` and `rebind`, and the member union
  holds only `m_error`. Every condition that [result.object] places on `T` in a *Constraints*,
  *Mandates* or *Remarks* element is taken to hold, with `T` treated as trivially copyable and as
  nothrow movable and swappable; so copy, move, assignment, `swap`, their `noexcept` and their
  triviality depend on `E` alone, and `result<void, E>` is trivially copyable if `E` is.
- (1.2) It has a default constructor, `constexpr result() noexcept`, which constructs a result
  whose `has_value()` is `true`. `return {};` therefore returns a success.
- (1.3) The constructor from `U&&` and the assignment from `U&&` are absent. For the constructor
  and assignment from `G&&`, *error-implicit*`<G>` is `std::is_convertible_v<G, E>`
  ([result.reqs] paragraph 4).
- (1.4) The constructor `constexpr explicit result(in_place_t) noexcept` takes no further
  arguments and has no `std::initializer_list` form.
- (1.5) The converting constructors take `result<U, G>` with `U` `void`, and the constructors and
  assignments from `success` take `success<void>`; the value is never the reason for an
  `explicit`.
- (1.6) Assignment and `swap` have the effects of [expected.void.assign] and [expected.void.swap]:
  giving an error to a result with a value constructs the error; giving a value to a result with an
  error destroys the error. Neither needs *reinit*.
- (1.7) There is no `operator->`, `value_or` or `std::initializer_list` form of `emplace`.
  `constexpr void emplace() noexcept` destroys the contained error, if any.
- (1.8) `constexpr void operator*() const noexcept` and `constexpr void value() const noexcept`
  have the precondition `has_value()` and no other effect.
- (1.9) The functions given to `and_then` and `transform` take no arguments; *VAL* is omitted from
  their invocation, and `or_else` and `transform_error` construct their success with
  `in_place` alone.
- (1.10) `operator==` compares with `result<void, E2>` (equal if both have a value, or if both have
  an error and the errors compare equal), with `success<void>` and with `failure<E2>`; there is no
  comparison with a value.

## 10 Partial specialization for reference values [result.ref]

1 `result<T&, E>` is specified by [result.object] with the following differences. Its value is
held as a pointer `T* m_value` (exposition only).

- (1.1) The constructor and the assignment from `U&&` have the constraints of
  [result.object.ctor] paragraph 10 with item (10.3) replaced by *binds-directly*`<U, T&>`; the
  assignment has no further constraint. The constructor is never explicit and initializes
  `m_value` with `std::addressof(v)`.
- (1.2) A further constructor `template <typename U> result(U&& v) = delete;` and assignment
  `template <typename U> result& operator=(U&& v) = delete;` are constrained on
  `std::remove_cvref_t<U>` not being a tag or a specialization of `result`, `success` or `failure`,
  `std::is_constructible_v<T&, U>` being `true` and *binds-directly*`<U, T&>` being `false`.
  *error-implicit*`<G>` ([result.reqs] paragraph 4) has `T&` for `T`, so it is `false` wherever
  these are viable and the two never compete. [Note 1: An argument that would bind `T&` to a
  temporary, such as `42` for `result<const int&, int>`, is therefore ill-formed rather than an
  error, in a `return` and in an assignment alike. — end note]
- (1.3) The converting constructors take `result<U&, G>` only, and the constructors from `success`
  take `success<U&>` only, each constrained on `std::is_convertible_v<U*, T*>`; the value part
  copies the pointer and is never the reason for an `explicit`.
- (1.4) The `in_place_t` constructor is `template <typename U> explicit result(in_place_t, U&& v)`,
  constrained on *binds-directly*`<U, T&>`.
- (1.5) Copy and move construction and assignment copy the pointer for the value. Their deletion,
  `noexcept` and triviality depend on `E` alone, with `T` treated as trivially copyable and
  nothrow movable.
- (1.6) Every assignment that gives the result a value rebinds `m_value` to the new referent, even
  if `has_value()` was `true`; no assignment writes through the reference. `emplace` is
  `template <typename U> T& emplace(U&& v) noexcept`, constrained on *binds-directly*`<U, T&>`,
  and rebinds in the same way. `swap` exchanges the pointers when both results have a value.
- (1.7) `operator->` is `constexpr T* operator->() const noexcept` and returns `m_value`. All four
  forms of `operator*` and `value()` return `T&`, which is `*m_value`: the constness of the result
  does not apply to the referent.
- (1.8) `value_or` returns `std::remove_cv_t<T>` by value, copied from `**this` in both overloads,
  with the copy-constructibility mandate on that type: an rvalue result does not own its referent,
  so nothing is moved from it.
- (1.9) In the monadic operations, *VAL* is `**this` for every overload, for the same reason.
- (1.10) `operator==` compares referents, never addresses.

[Note 2: Rebinding follows `std::optional<T&>` in C++26 (P2988). Assigning through would make
`r = x` change a value on one path and rebind on another, depending on `has_value()`. A write
through the reference is spelled `*r = x`. — end note]

## 11 Formatting [result.format]

```cpp
template <typename T, typename E>
struct std::formatter<forge::result<T, E>, char>;
template <typename T>
struct std::formatter<forge::success<T>, char>;
template <typename E>
struct std::formatter<forge::failure<E>, char>;
```

1 A type `X` is *formattable* here if `std::formatter<X, char>` is enabled
([format.formatter.spec]). The specialization for `result<T, E>` is enabled if and only if `E` and,
unless `T` is `void`, `std::remove_cvref_t<T>` are formattable; that for `success<T>` if and only
if `T` is `void` or `std::remove_cvref_t<T>` is formattable; that for `failure<E>` if and only if
`E` is formattable. A disabled specialization is as specified in [format.formatter.spec].

[Note 1: `std::formattable` is C++23; in C++20 each formatter is a partial specialization
constrained on `std::is_default_constructible_v<std::formatter<X, char>>`, which is `false` for a
disabled formatter. — end note]

2 `parse` is `constexpr`. If the format-spec is not empty, then: during constant evaluation, the
evaluation is not a constant expression; otherwise, if `FORGE_EXCEPTIONS_ENABLED` is 1, `parse`
throws `std::format_error`; otherwise, it evaluates `FORGE_UNREACHABLE`. [Note 2: In a format string
checked at compile time, such as a message of `FORGE_ASSERT`, a non-empty format-spec is therefore
ill-formed. — end note]

3 `format` writes, for a value `v` and an error `e` of the argument:

- (3.1) `success(`, then `v` as if by `std::format_to(out, "{}", v)`, then `)`, for a `success<T>`
  or a `result` with a value of a non-void type;
- (3.2) `success()` for a `success<void>` or a `result<void, E>` with a value;
- (3.3) `failure(`, then `e` as if by `std::format_to(out, "{}", e)`, then `)`, for a `failure<E>`
  or a `result` with an error.

For `T&`, `v` is the referent.

[Example 1: `std::format("{}", forge::result<int, std::string_view>(42))` is `success(42)`;
for the error `"count cannot be negative"` it is `failure(count cannot be negative)`.
— end example]

[Note 3: Strings are written without quotes or escapes: the debug format (`{:?}`) that would quote
them is C++23. — end note]

## Annex A (informative) Tests [result.tests]

1 `forge/unittests/core/result_test.cpp` is expected to check the following, each also in a
`static_assert` where the operation is a constant expression:

- (1.1) construction from a value, an implicitly convertible error, `success`, `failure`, both
  tags, and another `result`, with `has_value()`, `value()`, `operator*`, `operator->` and `error()`
  afterwards, for `result<T, E>`, `result<void, E>` and `result<T&, E>`;
- (1.2) the well-formed returns of [result.object.general] Example 1, `return 0;` for
  `result<std::size_t, std::errc>` and `result<double, std::errc>`, and
  `result<int, double>(3.5)` holding the value `3`;
- (1.3) each assignment between every pair of states, with a type that counts constructions and
  destructions, and, in the `exceptions` configuration, that a throwing creation restores the old
  state ([result.object.assign] paragraph 1);
- (1.4) that assignment to a `result<T&, E>` rebinds and never writes through, that its `swap`
  exchanges referents' addresses, and that its `value_or` on an rvalue copies;
- (1.5) `swap` between every pair of states, and `emplace` from each state;
- (1.6) `value_or`, `error_or`, and the four monadic operations with every value category and with
  `void` and reference results;
- (1.7) every `operator==`, including the rewritten `!=` and reversed forms;
- (1.8) `std::format` of each kind ([result.format] paragraph 3);
- (1.9) with the `asserts` feature, death tests that `value()`, `operator*`, `operator->` and
  `error()` in the wrong state write a failure report.

2 Tests in `forge/test/host/` are expected to check compile-time contracts with the consumer's
flags:

- (2.1) `result-traits.cpp`: triviality of the special members and trivial copyability
  ([result.object.ctor] paragraphs 4, 9 and 42; [result.object.assign] paragraphs 5 and 9;
  [result.void] item (1.1); [result.ref] item (1.5)); the `noexcept` expressions of
  [result.object.ctor] paragraph 9, [result.object.assign] paragraph 9 and [result.object.swap]
  paragraph 3; `std::is_convertible_v` and `std::is_constructible_v` for the cases of
  [result.reqs] paragraphs 3 and 4 and the explicitness of the converting constructors; that
  assignment exists for a type without a `noexcept` move constructor exactly when
  `FORGE_EXCEPTIONS_ENABLED` is 0; that `result<T, E>` is not default-constructible; and that each
  formatter is disabled for a non-formattable `T` or `E`;
- (2.2) `result-mandates.cpp`: that the ill-formed instantiations of [result.reqs] paragraph 1, the
  ill-formed returns of [result.object.general] Example 1, a binding to a temporary in a return and
  in an assignment ([result.ref] item (1.2)), `r = 3.5` for `result<int, double>`, `transform`
  returning a reference from an rvalue, a non-empty format-spec and a precondition violation during
  constant evaluation fail to compile, each matched on a diagnostic per host compiler;
- (2.3) `result-nodiscard.cpp`: that a discarded call that returns each class of this document
  warns, and, with `REQUIRES: host-cxx-clang`, that a discarded `forge::success{x};` does.

## Annex B (informative) Rationale [result.rationale]

### B.1 Prior art [result.rationale.prior]

| Project | Error type | Construction | Misuse | Remarks |
|---|---|---|---|---|
| `std::expected` (C++23; libstdc++ `include/std/expected`, libc++ `include/__expected/expected.h`) | Any `E` | Implicit from `T` when convertible; error only through `std::unexpected` | `value()` throws `bad_expected_access`; `operator*` has a precondition | No references; default-constructs `T`; monadic operations (P2505). |
| LLVM `Expected<T>` (`llvm/include/llvm/Support/Error.h`) | `Error`, a pointer to a heap-allocated `ErrorInfoBase` | Implicit from both `T` and `Error` | With `LLVM_ENABLE_ABI_BREAKING_CHECKS`, aborts if a result is destroyed unchecked | Supports `T&`; error kinds use LLVM's own RTTI. |
| LLVM `ErrorOr<T>` (`llvm/include/llvm/Support/ErrorOr.h`) | `std::error_code` | Implicit from both | `assert` on wrong-state access | Supports `T&`. |
| Abseil `StatusOr<T>` (`absl/status/statusor.h`) | `absl::Status` | Implicit from both | Terminates or throws | A fixed error type. |
| Rust `Result<T, E>` | Any `E` | `Ok(v)` / `Err(e)`, always explicit | `unwrap` panics | `#[must_use]`; the `?` operator propagates. |
| `std::optional<T&>` (C++26, P2988) | — | — | — | Assignment rebinds. |

1 Like LLVM, Abseil and C++23, forge converts implicitly from the value; like LLVM and Abseil, it
converts implicitly from the error too. It departs from all of them in how it settles an argument
that could be either ([result.reqs] paragraphs 3 and 4): it is never the error if `T` can be made
from it, and it is neither if it converts to `T` only by narrowing while `E` would accept it. So a
`bool` or arithmetic value type can neither swallow an error message nor lose a value to the error.
Narrowing is a property of the argument's type, not its value, so a rule that rejected every
narrowing conversion would also reject `return 0;` for a `std::size_t` value.

2 libstdc++ wrote `std::optional` before C++20 as a hierarchy of storage bases, one per
combination of trivial special members. C++20's conditionally trivial special members (P0848) make
that unnecessary, and every compiler at forge's floor (GCC 13, Clang 17, AppleClang 16, MSVC 19.44)
implements them; libstdc++'s and libc++'s `std::expected` use them likewise. The triviality that
matters is that of the destructor and of copy and move ([result.object.ctor] paragraph 42), which
on the Itanium C++ ABI decides whether a `result<int, errc>` is passed in registers: trivial
default construction is irrelevant, since `result` has no default constructor.

### B.2 Departures from `std::expected` [result.rationale.std]

| This document | `std::expected` | Reason |
|---|---|---|
| A C++20 header | C++23 | forge's baseline is C++20. |
| Wrong-state access is a `FORGE_ASSERT` precondition, also for `value()` | `value()` throws `bad_expected_access` | forge builds without exceptions by default; a failure report has a stack trace and crash context. |
| Implicit from an error that `T` cannot be made from | Only `std::unexpected` | `return "message";` reads as the error it is; ambiguous cases still need `failure`. |
| No implicit value when it narrows and `E` accepts the argument | `std::is_convertible` | `"oops"` cannot become `true`, nor `3.5` become `3` where `double` is the error type. |
| No default constructor except for `void` | Value-initializes `T` | A forgotten error must not look like a success. |
| No `U = T` default template argument on the value constructor | `U = T` (C++23; `remove_cv_t<T>` since LWG 3886) | It would make `r = {};` assign a value-initialized `T`, the success that the absent default constructor avoids. The cost is that `return {{a, b}};` needs `success`. |
| `result<T&, E>`, rebinding | No references | Lookups return references to objects that already exist, without a pointer that could be null. |
| `transform` on an lvalue may produce a `result<X&, E>` | Ill-formed for references | A consequence of allowing references; ill-formed on rvalues, where it would dangle. |
| Assignment and `emplace` without exceptions need no `noexcept` move | Same rule in every build | Nothing can throw, so nothing needs restoring. |
| `result<U&, G>` converts to `result<T, E>` explicitly, by copying | — | No silent copies. |
| `success` / `in_place_failure` | `std::unexpected` / `std::unexpect` | Names that say which state they select, alongside `failure`. |
| `std::formatter` | None in C++23 | Results in `FORGE_ASSERT` messages. |
| No conversions to or from `std::expected` | — | One result type in forge, the same at every `-std`. |

### B.3 Departures from LLVM [result.rationale.llvm]

| This document | LLVM | Reason |
|---|---|---|
| A static `E` | `Error`, type-erased on the heap | No allocation; no RTTI; the error type is part of the signature. |
| `[[nodiscard]]` only | Run-time "checked" flag with `LLVM_ENABLE_ABI_BREAKING_CHECKS` | The same layout and triviality in every configuration; a never-inspected local is rare enough not to justify a destructor with effects. |
| An argument that could be either needs `success` or `failure` | Any implicit conversion | As [result.rationale.prior] paragraph 1. |
| `T&` rebinds on assignment | `Expected<T&>` stores a `std::reference_wrapper` | Same effect, stated as a rule. |
| Monadic operations | `handleErrors`, `cantFail` and free functions | Follows the standard's vocabulary. |

### B.4 Relationship to later documents [result.rationale.future]

1 The error type of each fallible operation is left to the document for that operation
([result.scope] item (2.3)); `result` places no requirement on it beyond [result.defs] 2.4.

2 Once forge's baseline is C++23, [result.format] can write strings with the debug format, so that
they are quoted and escaped.

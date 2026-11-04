# Title [prefix]

Status: draft, YYYY-MM-DD.

## 0 Conventions [prefix.conventions]

1 This document follows the conventions of ISO/IEC 14882 [structure.specifications] and
[structure.summary]. A bracketed name such as [prefix.scope] is the stable name of a clause of this
document. Unqualified stable names such as [intro.defs] refer to ISO/IEC 14882.

2 Clauses 1 to N and Annex A are normative. Notes and examples in them are informative, as are
Annexes B and C.

3 The words "shall" and "shall not" state requirements on the implementation of forge. "Unspecified"
and "implementation-defined" have the meanings given in ISO/IEC 14882 [intro.defs]; an
implementation-defined property is documented in the source of the implementation.

## 1 Scope [prefix.scope]

1 This document specifies ...

2 The following are outside the scope of this document:

- (2.1) ...;
- (2.2) ....

## 2 Terms and definitions [prefix.defs]

**2.1 term**: definition.

## 3 Header `<forge/component/name.hpp>` synopsis [prefix.syn]

```cpp
#include "forge/core/config.hpp"

namespace forge {

// [prefix.facility], facility
FORGE_API void facility(int argument) noexcept;

} // namespace forge
```

1 The header declares no other names in namespace `forge`.

## 4 Facility [prefix.facility]

```cpp
void facility(int argument) noexcept;
```

1 *Preconditions*: ...

2 *Effects*: ...

3 *Returns*: ...

4 *Remarks*: ...

[Note 1: ... — end note]

## Annex A (normative) Build requirements [prefix.build]

1 ...

## Annex B (informative) Tests [prefix.tests]

1 `forge/unittests/component/name_test.cpp` is expected to check the following:

- (1.1) ...

## Annex C (informative) Rationale [prefix.rationale]

### C.1 Prior art [prefix.rationale.prior]

1 ...

### C.2 Departures from LLVM [prefix.rationale.llvm]

1 ...

### C.3 Relationship to later documents [prefix.rationale.future]

1 ...

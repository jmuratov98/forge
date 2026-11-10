"""M / L / A classes for the C-mode inventory.

Definitions are #9's:
  M  the semantics must be implemented correctly;
  L  a call to the same-named library function (or for abs the obvious
     expression) is a correct implementation outside constant evaluation;
  A  accepting the construct and ignoring it preserves behaviour.
A name #9 classified keeps #9's class unless an entry in CHANGES gives a
C-mode reason; every such change is listed in the report. Names #9 did not
classify get a class from NEW, with the reason.
"""

# Identifiers the extractor tracks that are not extension names of their own.
DROP_IDS = {
    "_Exit", "_exit",          # library functions GCC also knows as builtins
    "__VA_ARGS__",             # covered by the variadic-macro syntax rows
    "_Pragma",                 # covered by the pragma rows
    "__asm__",                 # covered by the asm rows
    "__const__",               # only ever the attribute name in __attribute__ ((__const__))
    "__has_attribute", "__has_builtin", "__has_extension",  # section 5 (query operators)
}

# display name here -> #9's name for the same construct
ALIAS = {"_Pragma (text from a macro argument)": "#pragma #"}

CHANGES = {
    "__signed__": ("M", "A in #9. `__signed__` is the keyword `signed`: the kernel's `typedef __signed__ char __s8;` "
                        "(asm-generic/int-ll64.h:20) needs a signed char, and plain char is unsigned on aarch64 "
                        "(`__CHAR_UNSIGNED__` is predefined), so ignoring the keyword changes the type. The reasoning "
                        "holds in C++ too; #9's A is corrected here."),
    "__inline": ("M", "A in #9. Under gnu89 glibc's `__extern_always_inline` is `extern __inline "
                      "__attribute__ ((__always_inline__))` without `gnu_inline` (sys/cdefs.h:618-628, "
                      "`__GNUC_GNU_INLINE__`), and <error.h> reaches such bodies at -O0 (bits/error.h). GNU89 "
                      "`extern inline` must not emit an out-of-line definition; dropping `__inline` turns the body "
                      "into an external definition of libc's `error`."),
}

NEW = {
    # attributes
    "nothrow": ("A", "In C glibc's `__THROW` is `__attribute__ ((__nothrow__ __LEAF))` (sys/cdefs.h:77-79); "
                     "it only lets the compiler assume no exception unwinds through the call. Not reached in #9 "
                     "because C++ uses `noexcept`."),
    "transparent_union": ("M", "`__SOCKADDR_ARG`/`__CONST_SOCKADDR_ARG` (sys/socket.h:80-84, `_GNU_SOURCE` only): "
                               "a call may pass any member type, which is otherwise an incompatible-pointer-types "
                               "error in GCC 14+ C."),
    "packed": ("M", "Changes struct layout (arpa/tftp.h:57-62, kernel UAPI structs)."),
    "indirect_return": ("A", "Marks `swapcontext` (ucontext.h:43, bits/indirect-return.h:30); only matters to "
                             "branch-target identification, which milestone 1 does not enable "
                             "(no -mbranch-protection in Ubuntu's cc1 defaults, data/facts/v-E-O0.txt)."),
    # keywords and types
    "bool": ("M", "C23 keyword for `_Bool` (stdbit.h declarations under gnu23)."),
    "_Generic": ("M", "glibc's `__glibc_const_generic` (sys/cdefs.h:837-840)."),
    "_Static_assert": ("M", "glibc's `static_assert` macro (assert.h)."),
    "_Thread_local": ("M", "glibc's `thread_local` macro (threads.h:34)."),
    "nullptr": ("M", "C23 `nullptr_t` in GCC's <stddef.h>."),
    "__typeof": ("M", "GNU typeof; same semantics as `__typeof__`."),
    "__inline__": ("A", "Kernel `static __inline__` helpers (linux/swab.h); `static` functions keep their meaning "
                        "when `inline` is ignored."),
    # builtins
    "__builtin_stdc_bit_ceil": ("M", "C23 <stdbit.h> type-generic builtin; no same-named library function."),
    "__builtin_aarch64_get_fpcr": ("M", "Reads FPCR (fpu_control.h `_FPU_GETCW`); no library function."),
    "__builtin_tgmath": ("M", "<tgmath.h> type-generic selection; no library function."),
    "__builtin_complex": ("M", "C11 `CMPLX*` (complex.h); builds a complex value, constant-foldable."),
    "__builtin_c23_va_start": ("M", "GCC's C23 `va_start` (stdarg.h)."),
    "__builtin_infd32": ("M", "Decimal-float constants in GCC's <float.h> (C23)."),
    # syntax
    "long long": ("M", "C99 type used in every dialect; under gnu89 an extension (`-Wlong-long`)."),
    "long long constant": ("M", "`LL`/`ULL` suffixes (sys/ifunc.h:86, linux/swab.h); C99, an extension under gnu89."),
    "anonymous struct or union member": ("M", "C11 feature (an extension under gnu89/gnu99): layout and member lookup."),
    "enum trailing comma": ("A", "C99 syntax; accepting the comma is the whole implementation."),
    "empty struct or union": ("M", "GNU extension with size 0 (kernel `__DECLARE_FLEX_ARRAY`)."),
    "variadic macro (__VA_ARGS__)": ("M", "C99 variadic macros (assert.h:156, GCC's stdarg.h:48)."),
    "#warning": ("A", "Diagnostic only (sys/elf.h:22); standard only from C23."),
    "#pragma GCC diagnostic": ("A", "Diagnostic state only."),
}

# family prefixes -> (class, reason) for NEW names that come in families
FAMILIES = [
    ("__builtin_stdc_", "__builtin_stdc_bit_ceil"),
    ("__builtin_aarch64_", "__builtin_aarch64_get_fpcr"),
    ("__builtin_nansd", "__builtin_infd32"),
    ("__builtin_nand", "__builtin_infd32"),
]


def group_of(nm):
    kind, _, base = nm.partition(":")
    if kind == "attr" or kind == "stdattr":
        return "attribute"
    if kind == "pragma":
        return "pragma"
    if kind == "asm":
        return "asm"
    if kind in ("syntax", "directive"):
        return "syntax"
    if base.startswith(("__builtin_", "__atomic_", "__sync_")):
        return "builtin"
    return "keyword"


def classify(nm, disp, hx9):
    g = group_of(nm)
    if disp in CHANGES:
        cls, why = CHANGES[disp]
        return cls, why, g
    if disp in NEW:
        cls, why = NEW[disp]
        return cls, why, g
    for pre, rep in FAMILIES:
        if disp.startswith(pre):
            return NEW[rep][0], NEW[rep][1], g
    if hx9 and hx9["class"] in ("M", "L", "A"):
        return hx9["class"], "#9's class", g
    return None, "", g

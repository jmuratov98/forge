/* Corrections from Apple clang 17's aarch64-linux-gnu predefines to GCC 15.2's,
   for -std=c++20 on aarch64 (default -march=armv8-a).  Each value is taken from
   gcc/c-family/c-cppbuiltin.cc and gcc/config/aarch64/aarch64-c.cc at tag
   releases/gcc-15.2.0.  Discovery aid only.  */

/* identity (also set on the command line) */
#undef __GNUG__
#define __GNUG__ 15

/* C++20 feature-test values that differ (c-cppbuiltin.cc cxx_dialect > cxx17 block) */
#undef __cpp_constexpr
#define __cpp_constexpr 202002L
#undef __cpp_deduction_guides
#define __cpp_deduction_guides 201907L
#undef __cpp_nontype_template_args
#define __cpp_nontype_template_args 201911L
/* GCC defines these only for cxx_dialect > cxx20 / > cxx23 */
#undef __cpp_static_call_operator
#undef __cpp_pack_indexing
/* GCC: if (flag_sized_deallocation), on by default for C++14 and later */
#define __cpp_sized_deallocation 201309L

/* clang-only preprocessor operators: GCC has no __is_identifier */
#undef __is_identifier

/* cpp_iec_559_value () == 2 for binary32/binary64 with default flags */
#define __GCC_IEC_559 2
#define __GCC_IEC_559_COMPLEX 2

/* c-cppbuiltin.cc: execution character sets (defaults UTF-8 / UTF-32LE) */
#define __GNUC_EXECUTION_CHARSET_NAME "UTF-8"
#define __GNUC_WIDE_EXECUTION_CHARSET_NAME "UTF-32LE"

/* builtin_define_type_minmax ("__WCHAR_MIN__", ...): wchar_t is unsigned int */
#define __WCHAR_MIN__ 0U
/* builtin_define_type_width ("__LONG_LONG_WIDTH__", ...) */
#define __LONG_LONG_WIDTH__ 64

/* _FloatN / _FloatNx / __bf16 constant families (builtin_define_float_constants);
   aarch64 has _Float16/32/64/128 and _Float32x/_Float64x, and bfloat16_type_node. */
#define __FLT32_MANT_DIG__ 24
#define __FLT32_DIG__ 6
#define __FLT32_MIN_EXP__ (-125)
#define __FLT32_MAX_EXP__ 128
#define __FLT64_MANT_DIG__ 53
#define __FLT64_DIG__ 15
#define __FLT64_MIN_EXP__ (-1021)
#define __FLT64_MAX_EXP__ 1024
#define __FLT128_MANT_DIG__ 113
#define __FLT128_DIG__ 33
#define __FLT128_MIN_EXP__ (-16381)
#define __FLT128_MAX_EXP__ 16384
#define __FLT32X_MANT_DIG__ 53
#define __FLT32X_DIG__ 15
#define __FLT64X_MANT_DIG__ 113
#define __FLT64X_DIG__ 33
#define __BFLT16_MANT_DIG__ 8
#define __BFLT16_DIG__ 2
#define __BFLT16_MIN_EXP__ (-125)
#define __BFLT16_MAX_EXP__ 128

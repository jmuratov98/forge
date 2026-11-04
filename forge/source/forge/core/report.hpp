// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include <cstddef>
#include <cstdio>

// What assert.cpp and crash_context.cpp share to write failure reports and live dumps.

namespace forge::detail {

// The frames a report's stack trace shows. One more is captured, which tells a truncated trace
// from one that just fits.
inline constexpr std::size_t g_report_frames = 32;

// Held while this thread writes a failure report or a live dump, so that output from several
// threads does not interleave: the others wait. A failure report never releases it, since the
// process aborts holding it. A thread that takes it a second time is in a check that failed while
// it was writing; it says so and aborts, where it would otherwise deadlock or recurse until its
// stack overflows.
class report_lock {
public:
    report_lock() noexcept;
    report_lock(const report_lock&) = delete;
    report_lock& operator=(const report_lock&) = delete;
    report_lock(report_lock&&) = delete;
    report_lock& operator=(report_lock&&) = delete;
    ~report_lock();

    // Whether the calling thread holds the lock.
    [[nodiscard]] static bool held() noexcept;
};

// Writes the calling thread's context to `file`, flushing it after each line
// ([context.chain] paragraph 2). Allocates nothing, given that entries' print functions do not.
void write_context(std::FILE* file) noexcept;

} // namespace forge::detail

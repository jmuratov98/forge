// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception

#pragma once

#include <gtest/gtest.h>

#include <algorithm>
#include <cstddef>
#include <ostream>
#include <regex>
#include <span>
#include <string>
#include <utility>
#include <vector>

// Matchers over what a failure report or a live dump writes, line by line. gtest's own regular
// expressions differ by host (POSIX on Linux and macOS, where `.` also matches a newline, and a
// small subset on Windows), so a pattern cannot stay within one line on every host; std::regex is
// the same everywhere. Each pattern matches a whole line. The "\r" that Windows writes to stderr
// before a newline is not part of the line.

namespace forge::test {

inline std::vector<std::string> lines_of(const std::string& text) {
    std::vector<std::string> lines;
    for (std::size_t begin = 0; begin < text.size();) {
        const std::size_t end = std::min(text.find('\n', begin), text.size());
        std::string line = text.substr(begin, end - begin);
        if (line.ends_with('\r')) {
            line.pop_back();
        }
        lines.push_back(std::move(line));
        begin = end + 1;
    }
    return lines;
}

// Matches text with consecutive lines that match `patterns` in order, or, when `present` is false,
// text with no such lines.
class lines_matcher final : public testing::MatcherInterface<const std::string&> {
public:
    lines_matcher(std::vector<std::string> patterns, bool present)
        : m_patterns(std::move(patterns)), m_present(present) {
        for (const std::string& pattern : m_patterns) {
            m_regexes.emplace_back(pattern);
        }
    }

    bool MatchAndExplain(const std::string& text,
                         testing::MatchResultListener* /*listener*/) const override {
        return found(lines_of(text)) == m_present;
    }

    void DescribeTo(std::ostream* os) const override {
        *os << (m_present ? "has" : "has no") << " consecutive lines matching";
        for (const std::string& pattern : m_patterns) {
            *os << "\n  " << pattern;
        }
    }

private:
    [[nodiscard]] bool found(const std::vector<std::string>& lines) const {
        const auto line_matches = [](const std::string& line, const std::regex& regex) {
            return std::regex_match(line, regex);
        };
        for (std::size_t first = 0; first + m_regexes.size() <= lines.size(); ++first) {
            if (std::ranges::equal(
                    std::span(lines).subspan(first, m_regexes.size()), m_regexes, line_matches)) {
                return true;
            }
        }
        return false;
    }

    std::vector<std::string> m_patterns;
    std::vector<std::regex> m_regexes;
    bool m_present;
};

inline testing::Matcher<const std::string&> has_lines(std::vector<std::string> patterns) {
    return testing::Matcher<const std::string&>(new lines_matcher(std::move(patterns), true));
}

inline testing::Matcher<const std::string&> has_no_line(std::string pattern) {
    return testing::Matcher<const std::string&>(new lines_matcher({std::move(pattern)}, false));
}

} // namespace forge::test

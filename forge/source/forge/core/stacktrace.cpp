#include "forge/core/stacktrace.hpp"

#include <algorithm>

namespace forge {

bool operator==(const stacktrace& x, const stacktrace& y) noexcept {
    return std::ranges::equal(x, y);
}

std::strong_ordering operator<=>(const stacktrace& x, const stacktrace& y) noexcept {
    if (auto s = x.size() <=> y.size(); s != 0) {
        return s;
    }
    return std::lexicographical_compare_three_way(x.begin(), x.end(), y.begin(), y.end());
}

} // namespace forge

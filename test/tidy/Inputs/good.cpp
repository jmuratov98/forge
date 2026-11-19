// Every kind of name, spelled as docs/style.md says.

#define FORGE_UPPER_SNAKE 1

namespace forge::sub_namespace {

struct source_location_like {
    int line_number;
};

class error_value {
public:
    int code() const { return m_code; }

private:
    int m_code = 0;
    static int s_instance_count;
};

union tagged_value {
    int as_int;
    char as_char;
};

enum class color_kind { red_tint, dark_blue };
enum plain_kind { plain_first, plain_second };

typedef int index_type;
using size_type = unsigned;

template <typename ValueType, int FixedSize>
struct fixed_array {
    ValueType items[FixedSize];
};

template <typename ValueType>
concept small_value = sizeof(ValueType) <= 8;

constexpr int max_align = 16;
const int default_limit = 4;
int g_crash_handler = 0;

int add_one(int input_value) {
    int local_total = input_value + 1;
    return local_total;
}

}  // namespace forge::sub_namespace

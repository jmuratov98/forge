#define lower_macro 1
#define MISSING_PREFIX 1
namespace BadNamespace {}
struct CamelStruct {};
class camelClass {};
union MixedUnion { int as_int; };
enum class BadEnum { fine_one };
enum class good_enum { BadEnumerator };
using BadAlias = int;
typedef int BadTypedef;
template <typename value_type> struct bad_template_parameter {};
template <typename ValueType>
concept BadConcept = true;
int BadFunction() { return 0; }
int badGlobal = 0;
int global_without_prefix = 0;
constexpr int BadConstexpr = 1;
void bad_parameter(int BadParam) {}
void bad_local() { int BadLocal = 0; (void)BadLocal; }
class private_members {
    int no_prefix;
    int BadCase_;
    static int no_static_prefix;
};

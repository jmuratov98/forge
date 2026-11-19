// A double mention in a comment, and "float" in a string, are not uses.
#include <cfloat>
#include <float.h>

const char* kind = "double";
const char* raw = R"x(float
double)x";
int doubled = 1'000;
int float_count = 2'0;
int my_double_value = 3;
char c = 'f';
/* float
   double */

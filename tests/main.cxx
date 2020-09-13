#include <stdio.h>

/** @brief This is a brief define description
 *
 * This is a detailed description that should be separated from
 * the brief description with one blank line.
 */
#define EXAMPLE_DEFINE_1 0xABCD

/// @brief This is one-line docummentation comment with brief description
#define EXAMPLE_DEFINE_2

/**
 * @brief This is a brief typedef description
 *
 * This is a detailed description that should be separated from
 * the brief description with one blank line.
 */
typedef int my_var;

/**
 * @brief This is a bief enum description
 *
 * This is a detailed description that should be separated from
 * the brief description with one blank line.
 *
 */
enum seasons {
  spring = 3, ///< Describes spring enum value
  summer,     ///< Describes summer enum value
  autumn = 7, ///< Describes autumn enum value
  winter      ///< Describes winter enum value
};

/// @brief This is a brief union description
union box {
  int var1;          ///< Describes var1 field
  double var2;       ///< Describes var2 field
  enum seasons var3; ///< Describes var3 field
};

class MyClass {
  public:
    int var;
};

int my_function(int a) {
  printf("My function");
}

int main(void) {

  printf("Hello World\n");
  return 0;
}

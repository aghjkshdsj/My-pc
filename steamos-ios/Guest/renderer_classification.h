#ifndef MPC_RENDERER_CLASSIFICATION_H
#define MPC_RENDERER_CLASSIFICATION_H
#include <ctype.h>
#include <stddef.h>

/* Some transport caps deliberately uppercase LLVMPIPE. Match without case. */
static int mpc_renderer_is_software(const char *name) {
    if (!name || !*name) return 1;
    static const char *tokens[] = { "llvmpipe", "lavapipe", "softpipe", "swiftshader", "software" };
    for (size_t token = 0; token < sizeof(tokens) / sizeof(tokens[0]); ++token)
        for (const char *start = name; *start; ++start) {
            size_t offset = 0;
            while (tokens[token][offset] && start[offset] &&
                   tolower((unsigned char)start[offset]) == tokens[token][offset]) ++offset;
            if (!tokens[token][offset]) return 1;
        }
    return 0;
}
#endif

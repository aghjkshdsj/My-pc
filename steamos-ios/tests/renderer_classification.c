/* Exercise driver strings that have hidden software fallback in transport caps. */
#include "../Guest/renderer_classification.h"
#include <stdio.h>

int main(void) {
    const char *rejected[] = { NULL, "", "llvmpipe (LLVM 20.1.2)", "virgl (LLVMPIPE)",
        "SoFtPiPe", "Google SwiftShader", "lavapipe", "Software Rasterizer" };
    const char *accepted[] = { "ANGLE (Apple, Apple A17 Pro, Metal)", "Apple A17 Pro", "AMD RADV" };
    for (size_t i = 0; i < sizeof(rejected) / sizeof(rejected[0]); ++i)
        if (!mpc_renderer_is_software(rejected[i])) return 1;
    for (size_t i = 0; i < sizeof(accepted) / sizeof(accepted[0]); ++i)
        if (mpc_renderer_is_software(accepted[i])) return 2;
    puts("RENDERER_REJECTION_OK: casing/transport strings cannot hide software fallback");
    return 0;
}

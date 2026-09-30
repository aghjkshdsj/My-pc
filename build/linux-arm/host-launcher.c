/* Test the SAME bridge and QEMU dylib used on iPhone, on an Apple Silicon Mac. */
#include "../../app/Madeira/LinuxVMBridge.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int frames;
static void frame(void *context, const void *pixels, int width, int height, int stride)
{
    if (pixels && width > 0 && height > 0 && stride >= width * 4) {
        if (!frames++) fprintf(stderr, "MYPC_APPLE_FRAMEBUFFER_OK %dx%d\n", width, height);
    }
}

int main(int argc, char **argv)
{
    if (argc < 3) {
        fprintf(stderr, "usage: host-launcher framework-binary qemu-options...\n");
        return 2;
    }
    char error[2048];
    char *library = argv[1];
    argv[1] = "qemu-system-aarch64";
    int result = spc_linux_run(library, argc - 1, argv + 1,
                              getenv("MYPC_TEST_DISPLAY") ? frame : NULL,
                              NULL, error, sizeof(error));
    if (*error) fprintf(stderr, "%s\n", error);
    return result < 0 ? 1 : result;
}

/* CI-only GPU readback test using the same iPhone bridge. GPL-3.0-or-later. */
#include "../../app/Madeira/LinuxVMBridge.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double previous;
static int announced;
static void frame(void *opaque, const void *pixels, int width, int height, int stride)
{
    (void)opaque;
    const char *path = getenv("MYPC_GPU_FRAME_PATH");
    if (!path || !pixels || width <= 0 || height <= 0 || width > 4096 ||
        height > 4096 || stride < width * 4 || stride > 4096 * 4) return;
    if (!announced) {
        announced = 1;
        fprintf(stderr, "MYPC_APPLE_FRAMEBUFFER_OK %dx%d\n", width, height);
        fflush(stderr);
    }
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now)) return;
    double seconds = now.tv_sec + now.tv_nsec / 1e9;
    if (seconds - previous < 1) return;
    previous = seconds;
    char temporary[4096];
    if (snprintf(temporary, sizeof(temporary), "%s.tmp", path) >= (int)sizeof(temporary)) return;
    FILE *file = fopen(temporary, "wb");
    if (!file) return;
    uint32_t header[] = {(uint32_t)width, (uint32_t)height, (uint32_t)stride};
    size_t bytes = (size_t)stride * height;
    int okay = fwrite(header, sizeof(header), 1, file) == 1 && fwrite(pixels, 1, bytes, file) == bytes;
    if (fclose(file)) okay = 0;
    if (okay) rename(temporary, path);
}

int main(int argc, char **argv)
{
    if (argc < 3) return 2;
    char error[2048];
    char *library = argv[1];
    argv[1] = "qemu-system-aarch64";
    int result = spc_linux_run(library, argc - 1, argv + 1, frame, NULL, error, sizeof(error));
    if (*error) fprintf(stderr, "%s\n", error);
    return result < 0 ? 1 : result;
}

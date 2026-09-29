/* Negative control: this is a CI host tool and is never bundled in the app. */
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>

int main(void)
{
    size_t size = (size_t)getpagesize();
    void *region = mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC,
                        MAP_PRIVATE | MAP_ANON | MAP_JIT, -1, 0);
    if (region != MAP_FAILED) {
        munmap(region, size);
        fputs("FAIL: hardened host permitted a JIT mapping\n", stderr);
        return 1;
    }
    puts("PASS: hardened host denies MAP_JIT without a JIT entitlement");
    return 0;
}

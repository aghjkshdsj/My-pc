/* Negative control for the CI policy; never bundled in the app. */
#include <dlfcn.h>
#include <errno.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stdio.h>

extern int mypc_nojit_policy_version(void);

int mypc_check_denied_jit(void)
{
    size_t size = (size_t)getpagesize();
    if (mypc_nojit_policy_version() != 1) return 1;
    void *region = mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC,
                        MAP_PRIVATE | MAP_ANON | MAP_JIT, -1, 0);
    if (region != MAP_FAILED || errno != EPERM) return 2;
    region = mmap(NULL, size, PROT_READ | PROT_WRITE | PROT_EXEC,
                  MAP_PRIVATE | MAP_ANON, -1, 0);
    if (region != MAP_FAILED || errno != EPERM) return 3;
    region = mmap(NULL, size, PROT_READ | PROT_WRITE,
                  MAP_PRIVATE | MAP_ANON, -1, 0);
    if (region == MAP_FAILED) return 4;
    *(volatile unsigned char *)region = 42;
    int result = 0;
    if (mprotect(region, size, PROT_READ | PROT_EXEC) != -1 || errno != EPERM) result = 5;
    if (mach_vm_protect(mach_task_self(), (mach_vm_address_t)region, size, FALSE,
                        VM_PROT_READ | VM_PROT_EXECUTE) != KERN_PROTECTION_FAILURE) result = 6;
    if (vm_protect(mach_task_self(), (vm_address_t)region, size, FALSE,
                   VM_PROT_READ | VM_PROT_EXECUTE) != KERN_PROTECTION_FAILURE) result = 7;
    if (mprotect(region, size, PROT_READ) != 0) result = 8;
    munmap(region, size);
    return result;
}

#ifndef MYPC_POLICY_PROBE
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    int result = mypc_check_denied_jit();
    if (result) {
        fprintf(stderr, "FAIL: CI memory policy negative control %d\n", result);
        return 1;
    }
    /* Prove interception in a library loaded exactly like QEMU. */
    void *library = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL | RTLD_FIRST);
    if (!library) { fputs("FAIL: cannot load CI policy probe\n", stderr); return 1; }
    int (*probe)(void) = (int (*)(void))dlsym(library, "mypc_check_denied_jit");
    if (!probe || (result = probe()) != 0) {
        fprintf(stderr, "FAIL: dlopened CI memory policy negative control %d\n", result);
        return 1;
    }
    puts("PASS: CI policy denies MAP_JIT, anonymous executable mappings and executable promotions in executable and dlopened library; writable data works");
    return 0;
}
#endif

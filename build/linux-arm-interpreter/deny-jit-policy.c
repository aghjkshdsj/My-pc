/* CI-only allocation policy. Never linked into or bundled with the iOS app.
 * A hosted Mac can permit MAP_JIT despite an ad-hoc hardened signature.
 * Interpose QEMU's allocation APIs, preserving signed file-backed code.
 */
#include <errno.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <stdatomic.h>
#include <stdio.h>
#include <sys/mman.h>

static _Atomic unsigned denied_requests;
int mypc_nojit_policy_version(void) { return 1; }

static void denied(void)
{
    atomic_fetch_add_explicit(&denied_requests, 1, memory_order_relaxed);
    fputs("MYPC_NOJIT_POLICY_DENIED\n", stderr);
}

static void *policy_mmap(void *address, size_t size, int protection,
                         int flags, int descriptor, off_t offset)
{
    if ((flags & MAP_JIT) || ((flags & MAP_ANON) && (protection & PROT_EXEC))) {
        denied();
        errno = EPERM;
        return MAP_FAILED;
    }
    return mmap(address, size, protection, flags, descriptor, offset);
}

static int policy_mprotect(void *address, size_t size, int protection)
{
    if (protection & PROT_EXEC) {
        denied();
        errno = EPERM;
        return -1;
    }
    return mprotect(address, size, protection);
}

static kern_return_t policy_mach_vm_protect(vm_map_t task, mach_vm_address_t address,
                                           mach_vm_size_t size, boolean_t maximum,
                                           vm_prot_t protection)
{
    if (task == mach_task_self() && (protection & VM_PROT_EXECUTE)) {
        denied();
        return KERN_PROTECTION_FAILURE;
    }
    return mach_vm_protect(task, address, size, maximum, protection);
}

static kern_return_t policy_vm_protect(vm_map_t task, vm_address_t address,
                                      vm_size_t size, boolean_t maximum,
                                      vm_prot_t protection)
{
    if (task == mach_task_self() && (protection & VM_PROT_EXECUTE)) {
        denied();
        return KERN_PROTECTION_FAILURE;
    }
    return vm_protect(task, address, size, maximum, protection);
}

/* The hosted SDK omits dyld-interposing.h. Emit its Mach-O tuple format
 * directly, avoiding any private API calls or injected environment variables.
 */
#define MYPC_INTERPOSE(replacement, original) \
    __attribute__((used, section("__DATA,__interpose"))) \
    static const struct { const void *replace; const void *with; } \
        mypc_interpose_##original = { (const void *)&replacement, (const void *)&original };
MYPC_INTERPOSE(policy_mmap, mmap)
MYPC_INTERPOSE(policy_mprotect, mprotect)
MYPC_INTERPOSE(policy_mach_vm_protect, mach_vm_protect)
MYPC_INTERPOSE(policy_vm_protect, vm_protect)

__attribute__((constructor)) static void policy_started(void)
{
    fputs("MYPC_NOJIT_POLICY_ACTIVE\n", stderr);
}

__attribute__((destructor)) static void policy_finished(void)
{
    fprintf(stderr, "MYPC_NOJIT_POLICY_SUMMARY denied_requests=%u\n",
            atomic_load_explicit(&denied_requests, memory_order_relaxed));
}

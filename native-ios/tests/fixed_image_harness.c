/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Runs the actual patched Wine claim/policy functions with host VM stubs. */
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <pthread.h>

typedef int BOOL;
typedef int kern_return_t;
typedef uintptr_t vm_address_t;
typedef size_t vm_size_t;
#define KERN_SUCCESS 0
#define IMAGE_FILE_MACHINE_AMD64 0x8664
#define IMAGE_FILE_RELOCS_STRIPPED 0x0001
#define IMAGE_FILE_DLL 0x2000
struct pe_image_info { uint64_t base; unsigned machine, image_charact; };
enum { IOS_EXEWIN_FREE, IOS_EXEWIN_CLAIMING, IOS_EXEWIN_OWNED,
       IOS_EXEWIN_RETIRING, IOS_EXEWIN_HELD_READY };
static uintptr_t ios_exe_win_base = UINT64_C(0x140000000);
static size_t ios_exe_win_size = 128u * 1024u * 1024u;
static int ios_exe_win_state = 1, ios_exewin_st = IOS_EXEWIN_FREE;
static void *ios_exe_win_held_base, *ios_exewin_pending_base;
static size_t ios_exe_win_held_size, ios_exewin_pending_size;
static pthread_mutex_t ios_exewin_lock = PTHREAD_MUTEX_INITIALIZER;
static unsigned deallocations;
static int vm_failure;
static size_t deallocated_size;
static int mach_task_self(void) { return 1; }
static void ios_exe_win_init(void) { ios_exe_win_state = 1; }
static const char *ios_exewin_state_name(int state) { (void)state; return "stub"; }
static kern_return_t vm_deallocate(int task, vm_address_t address, vm_size_t size)
{
    assert(task == 1 && address == ios_exe_win_base);
    ++deallocations; deallocated_size = size;
    return vm_failure;
}
static void ios_exe_win_note_pending(const void *base, size_t size)
{
    ios_exewin_pending_base = (void *)base; ios_exewin_pending_size = size;
    ios_exewin_st = IOS_EXEWIN_CLAIMING;
}

/* ACTUAL_WINE_FUNCTIONS */

static void reset(void)
{
    ios_exe_win_state = 1; ios_exewin_st = IOS_EXEWIN_FREE;
    ios_exe_win_held_base = ios_exewin_pending_base = NULL;
    ios_exe_win_held_size = ios_exewin_pending_size = 0;
    vm_failure = 0; deallocations = 0; deallocated_size = 0;
}

int main(void)
{
    void *base = (void *)ios_exe_win_base;
    const size_t dokimon_size = 0xa88000;
    struct pe_image_info game = {UINT64_C(0x140000000), 0x8664, 0x23};
    assert(ios_exe_win_fixed_main(&game, base, 0, 0));
    assert(!ios_exe_win_fixed_main(&game, NULL, 0, 0));
    assert(!ios_exe_win_fixed_main(&game, base, 1, 0));
    assert(!ios_exe_win_fixed_main(&game, base, 0, 1));
    assert(!ios_exe_win_fixed_main(&game, (void *)(ios_exe_win_base + 0x10000), 0, 0));
    game.machine = 0x14c; assert(!ios_exe_win_fixed_main(&game, base, 0, 0));
    game.machine = 0xaa64; assert(!ios_exe_win_fixed_main(&game, base, 0, 0));
    game.machine = 0x8664; game.image_charact = 0x22;
    assert(!ios_exe_win_fixed_main(&game, base, 0, 0));
    game.image_charact = 0x2023; assert(!ios_exe_win_fixed_main(&game, base, 0, 0));
    game.image_charact = 0x23;

    /* Reproduce the observed denial, then give this fixed image its address. */
    reset(); assert(!ios_exe_win_claim(base, dokimon_size, 0));
    assert(deallocations == 0 && ios_exe_win_state == 1);
    assert(ios_exe_win_claim(base, dokimon_size, ios_exe_win_fixed_main(&game, base, 0, 0)));
    assert(deallocations == 1 && ios_exe_win_state == 0);
    assert(ios_exewin_pending_base == base && ios_exewin_pending_size == dokimon_size);
    assert(ios_exewin_st == IOS_EXEWIN_CLAIMING);
    /* The anonymous map call cannot release a second interval. */
    assert(!ios_exe_win_claim(base, dokimon_size, 0) && deallocations == 1);
    reset(); assert(ios_exe_win_claim(base, 64u * 1024u * 1024u, 0));

    /* Empty, outside, overflowing and overlong intervals never release it. */
    reset(); assert(!ios_exe_win_claim(base, 0, 1));
    assert(!ios_exe_win_claim((void *)(ios_exe_win_base - 1), 1, 1));
    assert(!ios_exe_win_claim((void *)(ios_exe_win_base + ios_exe_win_size), 1, 1));
    assert(!ios_exe_win_claim(base, ios_exe_win_size + 1, 1));
    assert(!ios_exe_win_claim((void *)UINTPTR_MAX, 2, 1));
    assert(!ios_exe_win_claim(base, SIZE_MAX, 1)); assert(deallocations == 0);
    reset(); vm_failure = 3; assert(!ios_exe_win_claim(base, dokimon_size, 1));
    assert(ios_exe_win_state == 1 && ios_exewin_pending_base == NULL);

    /* A live/retiring owner cannot be evicted. Only the exact retired interval
       in HELD_READY may be granted, using that interval rather than the window. */
    reset(); ios_exe_win_state = 0; ios_exewin_st = IOS_EXEWIN_OWNED;
    assert(!ios_exe_win_claim(base, dokimon_size, 1) && deallocations == 0);
    ios_exe_win_held_base = base; ios_exe_win_held_size = dokimon_size;
    ios_exewin_st = IOS_EXEWIN_RETIRING;
    assert(!ios_exe_win_claim(base, dokimon_size, 1) && deallocations == 0);
    ios_exewin_st = IOS_EXEWIN_HELD_READY;
    assert(!ios_exe_win_claim(base, dokimon_size + 0x10000, 1) && deallocations == 0);
    assert(ios_exe_win_claim(base, dokimon_size, 1));
    assert(deallocations == 1 && deallocated_size == dokimon_size);
    assert(ios_exe_win_held_base == NULL && ios_exewin_st == IOS_EXEWIN_CLAIMING);
    assert(!ios_exe_win_claim(base, dokimon_size, 1) && deallocations == 1);
    puts("Fixed-image regression checks passed (actual Wine functions, VM stubs)");
    return 0;
}

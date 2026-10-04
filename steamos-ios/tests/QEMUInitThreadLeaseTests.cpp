// SPDX-License-Identifier: MIT
// Native thread/TLS ownership regression; this is not execution of QEMU or iOS.
#include "QEMUInitThreadLease.h"
#include <atomic>
#include <cassert>
#include <cstdio>
#include <stdexcept>
#include <thread>

static thread_local bool registered;
static std::atomic<unsigned> liveRegistrations{0}, unregistrations{0};
static void init() { assert(!registered); registered = true; ++liveRegistrations; }
static void unregisterRCU() {
    assert(registered);
    registered = false;
    --liveRegistrations;
    ++unregistrations;
}

int main() {
    { MPCQEMUInitThreadLease missing(nullptr); assert(!missing.initializedOnThisThread()); assert(!missing.retire()); }
    const unsigned rounds = 1000;
    for (unsigned i = 0; i < rounds; ++i) {
        std::thread worker([i] {
            MPCQEMUInitThreadLease lease(unregisterRCU);
            assert(!lease.retire()); // Must not unregister before qemu_init returns.
            init();
            assert(lease.initializedOnThisThread());
            assert(!lease.initializedOnThisThread()); // Never register twice.
            assert(registered && liveRegistrations == 1);
            std::thread unrelated([&lease] { assert(!lease.retire()); });
            unrelated.join();
            assert(registered && liveRegistrations == 1);
            if (i % 3 == 0) {
                assert(lease.retire() && lease.retired());
                assert(!lease.retire());
                assert(!lease.initializedOnThisThread());
                assert(!registered && liveRegistrations == 0);
            } // Other paths exercise destructor retirement before TLS disappears.
        });
        worker.join();
        assert(liveRegistrations == 0 && unregistrations == i + 1);
    }
    std::thread exceptional([] {
        try {
            MPCQEMUInitThreadLease lease(unregisterRCU);
            init(); assert(lease.initializedOnThisThread());
            throw std::runtime_error("unwind worker");
        } catch (const std::runtime_error &) { assert(!registered && liveRegistrations == 0); }
    });
    exceptional.join();
    assert(unregistrations == rounds + 1);
    // Negative control: an unretired registration remains, as in the old adapter.
    std::thread oldWorker([] { init(); }); oldWorker.join();
    assert(liveRegistrations == 1);
    liveRegistrations = 0; // Counter-only fixture; no dangling TLS is dereferenced.
    std::printf("QEMU init-thread lease: %u real thread retirements passed; missing, duplicate, wrong-thread and omitted retirement controls passed\n", rounds + 1);
}

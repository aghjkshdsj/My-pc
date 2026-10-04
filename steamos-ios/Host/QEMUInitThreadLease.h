// SPDX-License-Identifier: MIT
#pragma once
#include <thread>

// qemu_init registers this caller with RCU in the pinned shared-library build.
// Its TLS must stay alive until the same caller unregisters, before thread exit.
class MPCQEMUInitThreadLease final {
public:
    using Unregister = void (*)(void);
    explicit MPCQEMUInitThreadLease(Unregister unregister) noexcept : unregister_(unregister) {}
    MPCQEMUInitThreadLease(const MPCQEMUInitThreadLease &) = delete;
    MPCQEMUInitThreadLease &operator=(const MPCQEMUInitThreadLease &) = delete;
    ~MPCQEMUInitThreadLease() { if (active_) retire(); }

    bool initializedOnThisThread() noexcept {
        if (!unregister_ || active_ || retired_) return false;
        owner_ = std::this_thread::get_id();
        active_ = true;
        return true;
    }
    bool retire() noexcept {
        if (!active_ || owner_ != std::this_thread::get_id()) return false;
        unregister_();
        active_ = false;
        retired_ = true;
        return true;
    }
    bool retired() const noexcept { return retired_; }
private:
    Unregister unregister_;
    std::thread::id owner_;
    bool active_ = false, retired_ = false;
};

// Fresh MIT bounded completion ledger; caller serializes access.
#pragma once
#include <cmath>
#include <cstdint>
#include <string>
#include <vector>

struct MPCMetalTraceEntry {
    uint64_t token, registry;
    std::string device;
    bool completed = false, error = false;
    uint32_t status = 0;
    int64_t errorCode = 0;
    double start = 0, end = 0;
};
class MPCMetalTraceLedger {
public:
    static constexpr size_t capacity = 1024;
    std::vector<MPCMetalTraceEntry> entries;
    uint64_t overflow = 0, unknown = 0, duplicates = 0, identityErrors = 0;
    uint64_t initialErrors = 0, invalidTiming = 0;
    uint64_t observe(uint64_t registry, const char *name, bool error) {
        if (entries.size() >= capacity) { ++overflow; return 0; }
        if (error) ++initialErrors;
        std::string device = name ? name : "";
        if (!registry || device.empty()) ++identityErrors;
        uint64_t token = entries.size() + 1;
        entries.push_back({token, registry, device});
        return token;
    }
    void complete(uint64_t token, uint32_t status, bool error, int64_t errorCode,
                  uint64_t registry, const char *name, double start, double end) {
        if (!token || token > entries.size()) { ++unknown; return; }
        auto &entry = entries[token - 1];
        if (entry.completed) { ++duplicates; return; }
        if (registry != entry.registry || !name || entry.device != name) ++identityErrors;
        entry.completed = true; entry.status = status; entry.error = error;
        entry.errorCode = errorCode; entry.start = start; entry.end = end;
        if (!std::isfinite(start) || !std::isfinite(end) || start < 0 || end < start)
            ++invalidTiming;
    }
    size_t pending() const {
        size_t count = 0; for (const auto &entry : entries) if (!entry.completed) ++count;
        return count;
    }
    size_t failed() const {
        size_t count = 0;
        for (const auto &entry : entries) if (entry.completed && (entry.status != 4 || entry.error || entry.errorCode != 0)) ++count;
        return count;
    }
    size_t timed() const {
        size_t count = 0;
        for (const auto &entry : entries)
            if (entry.completed && entry.status == 4 && !entry.error && std::isfinite(entry.start) &&
                std::isfinite(entry.end) && entry.start > 0 && entry.end > entry.start) ++count;
        return count;
    }
    bool accepted(const std::string &expectedDevice) const {
        if (entries.size() < 2 || pending() || failed() || timed() < 2 || expectedDevice.empty() ||
            overflow || unknown || duplicates || identityErrors || initialErrors || invalidTiming) return false;
        for (const auto &entry : entries)
            if (entry.device != expectedDevice || entry.registry != entries.front().registry) return false;
        return true;
    }
};

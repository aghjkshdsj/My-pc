// Real production acceptance logic with rejection fixtures, not GPU proof.
#include "GuestMetalTraceLedger.h"
#include <cassert>
#include <cstdio>
#include <limits>
static MPCMetalTraceLedger fixture() {
    MPCMetalTraceLedger ledger;
    for (int i = 0; i < 2; ++i) {
        auto token = ledger.observe(99, "fixture", false);
        ledger.complete(token, 4, false, 0, 99, "fixture", 3 + i, 3.01 + i);
    }
    return ledger;
}
int main() {
    unsigned checks = 0;
    auto check = [&](bool condition) { ++checks; assert(condition); };
    check(fixture().accepted("fixture"));
    check(!fixture().accepted("different"));
    check(!MPCMetalTraceLedger{}.accepted("fixture"));
    auto ledger = fixture(); ledger.observe(99, "fixture", false); check(!ledger.accepted("fixture"));
    ledger = fixture(); ledger.complete(0, 4, false, 0, 99, "fixture", 3, 4); check(!ledger.accepted("fixture"));
    ledger = fixture(); ledger.complete(9, 4, false, 0, 99, "fixture", 3, 4); check(!ledger.accepted("fixture"));
    ledger = fixture(); ledger.complete(1, 4, false, 0, 99, "fixture", 3, 4); check(!ledger.accepted("fixture"));
    for (uint32_t status : {0u, 1u, 2u, 3u, 5u}) {
        ledger = fixture(); ledger.entries[0].status = status; check(!ledger.accepted("fixture"));
    }
    ledger = fixture(); ledger.entries[0].error = true; check(!ledger.accepted("fixture"));
    ledger = fixture(); ledger.entries[0].errorCode = 9; check(!ledger.accepted("fixture"));
    ledger = fixture(); ledger.observe(99, "fixture", true); check(!ledger.accepted("fixture"));
    ledger = fixture(); auto token = ledger.observe(99, "fixture", false);
    ledger.complete(token, 4, false, 0, 100, "fixture", 3, 4); check(!ledger.accepted("fixture"));
    ledger = fixture(); token = ledger.observe(99, "fixture", false);
    ledger.complete(token, 4, false, 0, 99, "other", 3, 4); check(!ledger.accepted("fixture"));
    for (double start : {0.0, -1.0, std::numeric_limits<double>::quiet_NaN(), std::numeric_limits<double>::infinity()}) {
        ledger = fixture(); ledger.entries[0].start = start; check(!ledger.accepted("fixture"));
    }
    ledger = fixture(); ledger.entries[0].end = ledger.entries[0].start; check(!ledger.accepted("fixture"));
    ledger = fixture(); token = ledger.observe(99, "fixture", false);
    ledger.complete(token, 4, false, 0, 99, "fixture", 4, 3); check(!ledger.accepted("fixture"));
    ledger = fixture(); token = ledger.observe(0, "", false);
    ledger.complete(token, 4, false, 0, 0, "", 3, 4); check(!ledger.accepted("fixture"));
    ledger = fixture();
    for (size_t i = ledger.entries.size(); i < MPCMetalTraceLedger::capacity + 1; ++i) ledger.observe(99, "fixture", false);
    check(ledger.entries.size() == MPCMetalTraceLedger::capacity && ledger.overflow == 1 && !ledger.accepted("fixture"));
    ledger = fixture(); token = ledger.observe(99, "fixture", false);
    ledger.complete(token, 4, false, 0, 99, "fixture", 7, 7);
    check(ledger.accepted("fixture") && ledger.timed() == 2 && ledger.invalidTiming == 0);
    ledger.entries[0].end = ledger.entries[0].start;
    check(!ledger.accepted("fixture") && ledger.timed() == 1);
    printf("GUEST_METAL_LEDGER_TESTS_PASSED checks=%u scope=rejection-fixtures-only GPU-proof=false\n", checks);
}

// Fresh MIT component for future mutable-buffer transport. No GPU proof.
#ifndef MPC_FRAME_LEASE_LEDGER_H
#define MPC_FRAME_LEASE_LEDGER_H
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace mpc {
struct FrameSession { uint64_t high = 0, low = 0; };
struct FrameLayout {
    uint32_t resource = 0, width = 0, height = 0, format = 0, stride = 0;
    uint64_t incarnation = 0, offset = 0, backingBytes = 0, registry = 0, alignment = 0;
};
struct FrameTicket {
    FrameSession session;
    uint64_t serial = 0, incarnation = 0;
    uint32_t resource = 0;
};
enum class LeaseResult { Ok, Busy, Stale, InvalidLayout, InvalidOwnership, InvalidState, Faulted, Overflow };
enum class LeaseState { Unregistered, Free, Producing, Ready, Consuming, ConsumerFinished, ReleaseSent };

// All methods run on one owning transport executor. A Metal completion callback
// must enqueue its observed result there. No GPU objects, waits, allocation or
// lock ownership are hidden in this table. It is not wired to scanout ABI1.
class FrameLeaseLedger {
public:
    static constexpr std::size_t capacity = 3, maximumConsumers = 2;
    explicit FrameLeaseLedger(FrameSession session, uint64_t registry)
        : session_(session), registry_(registry) {
        faulted_ = (!session.high && !session.low) || !registry;
    }
    LeaseResult registerBuffer(const FrameLayout &layout) {
        if (faulted_) return LeaseResult::Faulted;
        if (!validLayout(layout)) return LeaseResult::InvalidLayout;
        for (auto &slot : slots_) if (slot.layout.resource == layout.resource) return LeaseResult::InvalidState;
        for (auto &slot : slots_) if (slot.state == LeaseState::Unregistered) {
            slot.layout = layout; slot.state = LeaseState::Free; return LeaseResult::Ok;
        }
        return LeaseResult::Busy;
    }
    LeaseResult beginProducer(uint32_t resource, FrameTicket &ticket) {
        if (faulted_) return LeaseResult::Faulted;
        auto *slot = findResource(resource);
        if (!slot) return LeaseResult::Stale;
        if (slot->state != LeaseState::Free) return LeaseResult::Busy;
        if (nextFrame_ == std::numeric_limits<uint64_t>::max()) return LeaseResult::Overflow;
        slot->ticket = {session_, ++nextFrame_, slot->layout.incarnation, resource};
        slot->state = LeaseState::Producing; slot->release = 0;
        ticket = slot->ticket; return LeaseResult::Ok;
    }
    LeaseResult finishProducer(const FrameTicket &ticket, uint64_t completedFence, bool externalRelease) {
        auto *slot = findTicket(ticket);
        if (!slot) return LeaseResult::Stale;
        if (slot->state != LeaseState::Producing) return LeaseResult::InvalidState;
        if (!completedFence || !externalRelease) return LeaseResult::InvalidOwnership;
        slot->state = LeaseState::Ready; return LeaseResult::Ok;
    }
    LeaseResult beginConsumer(const FrameTicket &ticket, uint64_t observedRegistry) {
        auto *slot = findTicket(ticket);
        if (!slot) return LeaseResult::Stale;
        if (faulted_) return LeaseResult::Faulted;
        if (observedRegistry != registry_) return LeaseResult::InvalidOwnership;
        if (slot->state != LeaseState::Ready) return LeaseResult::InvalidState;
        if (consumers_ == maximumConsumers) return LeaseResult::Busy;
        slot->state = LeaseState::Consuming; ++consumers_; return LeaseResult::Ok;
    }
    LeaseResult finishConsumer(const FrameTicket &ticket, uint32_t observedStatus, bool hasError) {
        auto *slot = findTicket(ticket);
        if (!slot) return LeaseResult::Stale;
        if (slot->state != LeaseState::Consuming) return LeaseResult::InvalidState;
        // Metal Completed(4) and Error(5) are terminal. Errors stop new work,
        // but terminal callbacks still allow outstanding sources to be drained.
        if (observedStatus != 4 && observedStatus != 5) return LeaseResult::InvalidState;
        slot->state = LeaseState::ConsumerFinished; --consumers_;
        if (observedStatus == 5 || hasError) faulted_ = true;
        return LeaseResult::Ok;
    }
    LeaseResult issueRelease(const FrameTicket &ticket, uint64_t &release) {
        auto *slot = findTicket(ticket);
        if (!slot) return LeaseResult::Stale;
        // Ready is an explicitly dropped frame with no native GPU reader.
        // Consuming/Producing/ReleaseSent cannot be released by a CPU timeout.
        if (slot->state != LeaseState::Ready && slot->state != LeaseState::ConsumerFinished)
            return LeaseResult::InvalidState;
        if (nextRelease_ == std::numeric_limits<uint64_t>::max()) return LeaseResult::Overflow;
        slot->release = ++nextRelease_; slot->state = LeaseState::ReleaseSent;
        release = slot->release; return LeaseResult::Ok;
    }
    LeaseResult acknowledgeRelease(const FrameTicket &ticket, uint64_t release) {
        auto *slot = findTicket(ticket);
        if (!slot) return LeaseResult::Stale;
        if (slot->state != LeaseState::ReleaseSent) return LeaseResult::InvalidState;
        if (!release || release != slot->release) return LeaseResult::InvalidOwnership;
        slot->state = LeaseState::Free; return LeaseResult::Ok;
    }
    void quarantine() { faulted_ = true; }
    bool drained() const {
        for (const auto &slot : slots_)
            if (slot.state != LeaseState::Free && slot.state != LeaseState::Unregistered) return false;
        return consumers_ == 0;
    }
    bool faulted() const { return faulted_; }
    std::size_t consumers() const { return consumers_; }
    std::size_t registered() const {
        std::size_t count = 0;
        for (const auto &slot : slots_) if (slot.state != LeaseState::Unregistered) ++count;
        return count;
    }
    LeaseState state(uint32_t resource) const {
        for (const auto &slot : slots_) if (slot.layout.resource == resource) return slot.state;
        return LeaseState::Unregistered;
    }
private:
    struct Slot {
        FrameLayout layout;
        FrameTicket ticket;
        uint64_t release = 0;
        LeaseState state = LeaseState::Unregistered;
    };
    std::array<Slot, capacity> slots_{};
    FrameSession session_;
    uint64_t registry_ = 0, nextFrame_ = 0, nextRelease_ = 0;
    std::size_t consumers_ = 0;
    bool faulted_ = false;
    bool validLayout(const FrameLayout &l) const {
        // Initial transport contract: 720p linear BGRA8 on one real device.
        // Alignment comes from that device's linear-texture query, not iOS's
        // VM page size. The adapter remains responsible for alias verification.
        if (!l.resource || !l.incarnation || l.width != 1280 || l.height != 720 || l.format != 80 ||
            l.registry != registry_ || !l.alignment || l.alignment > 65536 ||
            (l.alignment & (l.alignment - 1)) || l.stride < 5120 || l.stride > (1u << 20) ||
            l.stride % l.alignment || l.offset % l.alignment || l.backingBytes > 64u * 1024u * 1024u ||
            l.offset > l.backingBytes) return false;
        const uint64_t span = uint64_t(l.stride) * l.height;
        return span <= l.backingBytes - l.offset;
    }
    Slot *findResource(uint32_t resource) {
        if (!resource) return nullptr;
        for (auto &slot : slots_)
            if (slot.state != LeaseState::Unregistered && slot.layout.resource == resource) return &slot;
        return nullptr;
    }
    Slot *findTicket(const FrameTicket &ticket) {
        if (!ticket.serial || ticket.session.high != session_.high || ticket.session.low != session_.low) return nullptr;
        auto *slot = findResource(ticket.resource);
        return slot && slot->ticket.serial == ticket.serial && slot->layout.incarnation == ticket.incarnation ? slot : nullptr;
    }
};
}
#endif

// Fresh MIT: classify display refreshes without granting a buffer release.
#ifndef MPC_MOVING_FRAME_REFRESH_H
#define MPC_MOVING_FRAME_REFRESH_H
#include "FrameLeaseLedger.h"
namespace mpc {
enum class MovingFlushDecision { Consume, RefreshOnly, Reject };
inline MovingFlushDecision classifyMovingFlush(FrameSession session, const FrameTicket &resource,
    const FrameTicket &armed, uint64_t lastConsumedSerial, LeaseState state) {
    if ((!session.high && !session.low) || resource.session.high != session.high ||
        resource.session.low != session.low || !resource.resource || !resource.serial ||
        resource.incarnation != 1 || state == LeaseState::Unregistered || state == LeaseState::Producing)
        return MovingFlushDecision::Reject;
    // A reinstalled display surface can flush the same content ticket again.
    // Skip that reader only; its existing GPU completion/release is untouched.
    if (lastConsumedSerial == resource.serial) return MovingFlushDecision::RefreshOnly;
    if (state != LeaseState::Ready || armed.session.high != session.high || armed.session.low != session.low ||
        armed.resource != resource.resource || armed.serial != resource.serial || armed.incarnation != resource.incarnation)
        return MovingFlushDecision::Reject;
    return MovingFlushDecision::Consume;
}
}
#endif

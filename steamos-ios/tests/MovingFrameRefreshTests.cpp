#include "../Engine/MovingFrameRefresh.h"
#include <cstdio>
#include <cstdlib>
static unsigned checks;
static void check(bool value) { ++checks; if (!value) std::abort(); }
int main() {
    using namespace mpc;
    FrameSession session{123,456}; FrameLeaseLedger ledger(session,99);
    for (unsigned r=9;r<12;++r) check(ledger.registerBuffer({r,1280,720,80,5120,1,0,3686400,99,16})==LeaseResult::Ok);
    FrameTicket first,second;
    check(ledger.beginProducer(9,first)==LeaseResult::Ok);
    check(classifyMovingFlush(session,first,first,0,ledger.state(9))==MovingFlushDecision::Reject);
    check(ledger.finishProducer(first,1,true)==LeaseResult::Ok);
    check(classifyMovingFlush(session,first,first,0,ledger.state(9))==MovingFlushDecision::Consume);
    check(ledger.beginConsumer(first,99)==LeaseResult::Ok);
    // INSTALL/FLUSH/DISABLE, then another INSTALL/FLUSH of the same resource:
    // the second generation must not create another reader or grant reuse.
    check(classifyMovingFlush(session,first,first,1,ledger.state(9))==MovingFlushDecision::RefreshOnly);
    uint64_t release=0;
    check(ledger.issueRelease(first,release)==LeaseResult::InvalidState);
    check(ledger.beginProducer(9,second)==LeaseResult::Busy);
    check(ledger.finishConsumer(first,4,false)==LeaseResult::Ok);
    check(ledger.issueRelease(first,release)==LeaseResult::Ok);
    check(classifyMovingFlush(session,first,first,1,ledger.state(9))==MovingFlushDecision::RefreshOnly);
    check(ledger.beginProducer(9,second)==LeaseResult::Busy);
    check(ledger.beginProducer(10,second)==LeaseResult::Ok);
    check(ledger.finishProducer(second,2,true)==LeaseResult::Ok);
    check(classifyMovingFlush(session,first,second,1,ledger.state(9))==MovingFlushDecision::RefreshOnly);
    check(classifyMovingFlush(session,second,second,0,ledger.state(10))==MovingFlushDecision::Consume);
    check(ledger.acknowledgeRelease(first,release)==LeaseResult::Ok);
    FrameTicket reused; check(ledger.beginProducer(9,reused)==LeaseResult::Ok);
    check(ledger.finishProducer(reused,3,true)==LeaseResult::Ok);
    check(classifyMovingFlush(session,reused,reused,1,ledger.state(9))==MovingFlushDecision::Consume);
    check(classifyMovingFlush(session,reused,first,1,ledger.state(9))==MovingFlushDecision::Reject);
    FrameTicket stale=reused; stale.session.low++;
    check(classifyMovingFlush(session,stale,reused,stale.serial,LeaseState::ReleaseSent)==MovingFlushDecision::Reject);
    stale=reused; stale.incarnation=2;
    check(classifyMovingFlush(session,stale,reused,stale.serial,LeaseState::ReleaseSent)==MovingFlushDecision::Reject);
    check(classifyMovingFlush(session,reused,reused,reused.serial,LeaseState::Unregistered)==MovingFlushDecision::Reject);
    check(classifyMovingFlush(session,reused,second,0,LeaseState::Ready)==MovingFlushDecision::Reject);
    std::printf("MOVING_REFRESH_TESTS_PASSED checks=%u same-resource-reinstallation-replayed GPU-proof=false\n",checks);
}

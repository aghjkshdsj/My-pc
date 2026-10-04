// Exercise real lease rules, not GPU/phone/WSI mocks. Synthetic values only.
#include "../Engine/FrameLeaseLedger.h"
#include <cstdio>
#include <cstdlib>
#include <vector>
using namespace mpc;
static uint64_t checks = 0;
#define CHECK(value) do { ++checks; if (!(value)) { std::fprintf(stderr,"lease check failed line=%d\n",__LINE__); std::exit(1); } } while (0)
static FrameLayout layout(uint32_t resource) {
    return {resource,1280,720,80,5120,1,0,3686400,99,16};
}
static FrameLeaseLedger pool() {
    FrameLeaseLedger ledger({1,2},99);
    for (uint32_t id=1; id<=3; ++id) CHECK(ledger.registerBuffer(layout(id))==LeaseResult::Ok);
    return ledger;
}
static FrameTicket ready(FrameLeaseLedger &ledger,uint32_t resource) {
    FrameTicket ticket;
    CHECK(ledger.beginProducer(resource,ticket)==LeaseResult::Ok);
    CHECK(ledger.finishProducer(ticket,7,true)==LeaseResult::Ok);
    return ticket;
}
int main() {
    CHECK(sizeof(FrameLeaseLedger)<4096);
    auto ledger=pool();CHECK(ledger.registered()==3 && ledger.drained());
    CHECK(ledger.registerBuffer(layout(4))==LeaseResult::Busy);
    CHECK(ledger.registerBuffer(layout(1))==LeaseResult::InvalidState);
    for (int mode=0; mode<10; ++mode) {
        FrameLeaseLedger invalid({1,2},99);auto bad=layout(1);
        switch (mode) {
        case 0:bad.resource=0;break;case 1:bad.width=1;break;case 2:bad.format=70;break;
        case 3:bad.registry=100;break;case 4:bad.alignment=3;break;case 5:bad.stride=1;break;
        case 6:bad.offset=UINT64_MAX;break;case 7:bad.backingBytes=3686399;break;
        case 8:bad.incarnation=0;break;case 9:bad.backingBytes=UINT64_MAX;break;
        }
        CHECK(invalid.registerBuffer(bad)==LeaseResult::InvalidLayout && invalid.drained());
    }
    FrameTicket first;CHECK(ledger.beginProducer(1,first)==LeaseResult::Ok);
    uint64_t release=0;FrameTicket unused;
    CHECK(ledger.beginProducer(1,unused)==LeaseResult::Busy);
    CHECK(ledger.beginConsumer(first,99)==LeaseResult::InvalidState);
    CHECK(ledger.issueRelease(first,release)==LeaseResult::InvalidState);
    CHECK(ledger.finishProducer(first,0,true)==LeaseResult::InvalidOwnership);
    CHECK(ledger.finishProducer(first,1,false)==LeaseResult::InvalidOwnership);
    CHECK(ledger.finishProducer(first,1,true)==LeaseResult::Ok);
    CHECK(ledger.beginConsumer(first,100)==LeaseResult::InvalidOwnership);
    CHECK(ledger.beginConsumer(first,99)==LeaseResult::Ok);
    CHECK(ledger.issueRelease(first,release)==LeaseResult::InvalidState);
    CHECK(ledger.finishConsumer(first,3,false)==LeaseResult::InvalidState && ledger.consumers()==1);
    auto second=ready(ledger,2),third=ready(ledger,3);
    CHECK(ledger.beginConsumer(second,99)==LeaseResult::Ok);
    CHECK(ledger.beginConsumer(third,99)==LeaseResult::Busy && ledger.consumers()==2);
    // Callbacks may finish in reverse order. They release only their own lease.
    CHECK(ledger.finishConsumer(second,4,false)==LeaseResult::Ok);
    CHECK(ledger.beginProducer(2,unused)==LeaseResult::Busy);
    CHECK(ledger.issueRelease(second,release)==LeaseResult::Ok);
    CHECK(ledger.acknowledgeRelease(second,release+1)==LeaseResult::InvalidOwnership);
    CHECK(ledger.acknowledgeRelease(first,release)==LeaseResult::InvalidState);
    CHECK(ledger.acknowledgeRelease(second,release)==LeaseResult::Ok);
    CHECK(ledger.acknowledgeRelease(second,release)==LeaseResult::InvalidState);
    auto reincarnated=ready(ledger,2);
    CHECK(reincarnated.serial>second.serial && reincarnated.resource==second.resource);
    CHECK(ledger.finishConsumer(second,4,false)==LeaseResult::Stale);
    CHECK(ledger.finishConsumer(first,4,false)==LeaseResult::Ok);
    CHECK(ledger.finishConsumer(first,4,false)==LeaseResult::InvalidState);
    CHECK(ledger.issueRelease(first,release)==LeaseResult::Ok);
    CHECK(ledger.acknowledgeRelease(first,release)==LeaseResult::Ok);
    for (auto ticket:{third,reincarnated}) {
        CHECK(ledger.issueRelease(ticket,release)==LeaseResult::Ok); // Drop before GPU submit.
        CHECK(ledger.acknowledgeRelease(ticket,release)==LeaseResult::Ok);
    }
    CHECK(ledger.drained());
    auto stale=first;stale.session.low=9;CHECK(ledger.finishConsumer(stale,4,false)==LeaseResult::Stale);
    stale=first;stale.incarnation=2;CHECK(ledger.issueRelease(stale,release)==LeaseResult::Stale);
    // A timeout/background loss stops new work without inventing completion.
    ledger=pool();first=ready(ledger,1);CHECK(ledger.beginConsumer(first,99)==LeaseResult::Ok);
    ledger.quarantine();CHECK(!ledger.drained() && ledger.faulted());
    CHECK(ledger.beginProducer(2,unused)==LeaseResult::Faulted);
    CHECK(ledger.issueRelease(first,release)==LeaseResult::InvalidState);
    CHECK(ledger.finishConsumer(first,4,false)==LeaseResult::Ok);
    CHECK(ledger.issueRelease(first,release)==LeaseResult::Ok);
    CHECK(ledger.acknowledgeRelease(first,release)==LeaseResult::Ok && ledger.drained());
    ledger=pool();first=ready(ledger,1);CHECK(ledger.beginConsumer(first,99)==LeaseResult::Ok);
    FrameTicket stillProducing;CHECK(ledger.beginProducer(2,stillProducing)==LeaseResult::Ok);
    CHECK(ledger.finishConsumer(first,5,true)==LeaseResult::Ok && ledger.faulted());
    CHECK(ledger.beginProducer(3,unused)==LeaseResult::Faulted);
    CHECK(ledger.issueRelease(first,release)==LeaseResult::Ok);
    CHECK(ledger.acknowledgeRelease(first,release)==LeaseResult::Ok && !ledger.drained());
    // Quarantine blocks new work but still accepts actual outstanding producer
    // completion so teardown can drain without inventing GPU completion.
    CHECK(ledger.finishProducer(stillProducing,9,true)==LeaseResult::Ok);
    CHECK(ledger.beginConsumer(stillProducing,99)==LeaseResult::Faulted);
    CHECK(ledger.issueRelease(stillProducing,release)==LeaseResult::Ok);
    CHECK(ledger.acknowledgeRelease(stillProducing,release)==LeaseResult::Ok && ledger.drained());
    // Long reuse with stable resource IDs and changing frame serials. Delayed
    // acknowledgements cannot retire a subsequent incarnation of the contents.
    ledger=pool();FrameTicket prior{};uint64_t priorRelease=0;
    for (uint64_t frame=0; frame<100000; ++frame) {
        auto ticket=ready(ledger,uint32_t(frame%3)+1);
        CHECK(ticket.serial==frame+1 && ledger.registered()==3);
        CHECK(ledger.beginConsumer(ticket,99)==LeaseResult::Ok);
        CHECK(ledger.beginProducer(ticket.resource,unused)==LeaseResult::Busy);
        CHECK(ledger.finishConsumer(ticket,4,false)==LeaseResult::Ok);
        CHECK(ledger.issueRelease(ticket,release)==LeaseResult::Ok);
        CHECK(ledger.acknowledgeRelease(ticket,release+1)==LeaseResult::InvalidOwnership);
        CHECK(ledger.acknowledgeRelease(prior,priorRelease)!=LeaseResult::Ok);
        CHECK(ledger.acknowledgeRelease(ticket,release)==LeaseResult::Ok);
        CHECK(ledger.drained() && ledger.consumers()==0);
        prior=ticket;priorRelease=release;
    }
    std::printf("FRAME_LEASE_TESTS_PASSED checks=%llu reused_frames=100000 scope=source-contract-only GPU-proof=false phone-tested=false\n",(unsigned long long)checks);
}

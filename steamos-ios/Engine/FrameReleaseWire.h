/* Fresh fixed-size release messages, MIT. Identity/integrity are not attestation. */
#ifndef MPC_FRAME_RELEASE_WIRE_H
#define MPC_FRAME_RELEASE_WIRE_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
enum { MPC_RELEASE_WIRE_BYTES = 80, MPC_RELEASE_WIRE_ABI = 1,
    MPC_RELEASE_REGISTERED = 1, MPC_RELEASE_ARMED = 2, MPC_RELEASE_COMPLETED = 3,
    MPC_RELEASE_REACQUIRED = 4, MPC_RELEASE_FINISHED = 5, MPC_RELEASE_CHANNEL_PROBE = 6 };
typedef struct MPCReleaseMessage {
    uint64_t session_high, session_low, serial, incarnation, release, registry;
    uint32_t resource, code, kind;
} MPCReleaseMessage;
static inline void mpc_wire_put32(unsigned char *p, uint32_t v) {
    for (unsigned i = 0; i < 4; ++i) p[i] = (unsigned char)(v >> (24u - 8u * i));
}
static inline uint32_t mpc_wire_get32(const unsigned char *p) {
    uint32_t v = 0; for (unsigned i = 0; i < 4; ++i) v = (v << 8) | p[i]; return v;
}
static inline void mpc_wire_put64(unsigned char *p, uint64_t v) {
    for (unsigned i = 0; i < 8; ++i) p[i] = (unsigned char)(v >> (56u - 8u * i));
}
static inline uint64_t mpc_wire_get64(const unsigned char *p) {
    uint64_t v = 0; for (unsigned i = 0; i < 8; ++i) v = (v << 8) | p[i]; return v;
}
static inline uint32_t mpc_wire_crc(const unsigned char *p, size_t count) {
    uint32_t crc = UINT32_MAX;
    for (size_t i = 0; i < count; ++i) {
        crc ^= p[i];
        for (unsigned bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ (UINT32_C(0xedb88320) & (0u - (crc & 1u)));
    }
    return ~crc;
}
static inline int mpc_wire_encode(const MPCReleaseMessage *m, unsigned char *p, size_t count) {
    if (!m || !p || count != MPC_RELEASE_WIRE_BYTES || (!m->session_high && !m->session_low) ||
        m->kind < 1 || m->kind > MPC_RELEASE_CHANNEL_PROBE) return 0;
    memset(p, 0, count);
    mpc_wire_put32(p, UINT32_C(0x4d504352));
    mpc_wire_put32(p + 4, (MPC_RELEASE_WIRE_ABI << 16) | m->kind);
    mpc_wire_put64(p + 8, m->session_high); mpc_wire_put64(p + 16, m->session_low);
    mpc_wire_put64(p + 24, m->serial); mpc_wire_put64(p + 32, m->incarnation);
    mpc_wire_put64(p + 40, m->release); mpc_wire_put64(p + 48, m->registry);
    mpc_wire_put32(p + 56, m->resource); mpc_wire_put32(p + 60, m->code);
    mpc_wire_put32(p + 72, mpc_wire_crc(p, 72)); mpc_wire_put32(p + 76, MPC_RELEASE_WIRE_BYTES);
    return 1;
}
static inline int mpc_wire_decode(const unsigned char *p, size_t count, MPCReleaseMessage *m) {
    if (!m || !p || count != MPC_RELEASE_WIRE_BYTES || mpc_wire_get32(p) != UINT32_C(0x4d504352) ||
        (mpc_wire_get32(p + 4) >> 16) != MPC_RELEASE_WIRE_ABI || mpc_wire_get32(p + 76) != count ||
        mpc_wire_get64(p + 64) || mpc_wire_get32(p + 72) != mpc_wire_crc(p, 72)) return 0;
    MPCReleaseMessage decoded = {mpc_wire_get64(p + 8), mpc_wire_get64(p + 16),
        mpc_wire_get64(p + 24), mpc_wire_get64(p + 32), mpc_wire_get64(p + 40), mpc_wire_get64(p + 48),
        mpc_wire_get32(p + 56), mpc_wire_get32(p + 60), mpc_wire_get32(p + 4) & 65535u};
    if ((!decoded.session_high && !decoded.session_low) || decoded.kind < 1 || decoded.kind > MPC_RELEASE_CHANNEL_PROBE) return 0;
    *m = decoded; return 1;
}
static inline int mpc_wire_identity(const MPCReleaseMessage *m, const MPCReleaseMessage *expected) {
    return m && expected && m->session_high == expected->session_high && m->session_low == expected->session_low &&
        m->serial == expected->serial && m->incarnation == expected->incarnation && m->resource == expected->resource &&
        m->kind == expected->kind;
}
static inline int mpc_wire_session(const char *nonce, uint64_t *high, uint64_t *low) {
    if (!nonce || !high || !low || strlen(nonce) != 32) return 0;
    uint64_t halves[2] = {0,0};
    for (unsigned i = 0; i < 32; ++i) {
        unsigned char c = (unsigned char)nonce[i];
        unsigned v = c >= '0' && c <= '9' ? (unsigned)(c - '0') : c >= 'a' && c <= 'f' ? (unsigned)(c - 'a') + 10u : 99u;
        if (v > 15u) return 0;
        halves[i / 16] = (halves[i / 16] << 4) | v;
    }
    if (!halves[0] && !halves[1]) return 0;
    *high = halves[0]; *low = halves[1]; return 1;
}
#endif

/* Fresh diagnostic guest release channel, MIT. Full KMS/WSI integration is separate. */
#ifndef MPC_FRAME_RELEASE_CHANNEL_H
#define MPC_FRAME_RELEASE_CHANNEL_H
#include "../Engine/FrameReleaseWire.h"
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>
typedef struct MPCGuestChannel { int fd; struct termios previous; } MPCGuestChannel;
static inline int mpc_channel_open(MPCGuestChannel *channel) {
    channel->fd = open("/dev/ttyAMA0", O_RDWR | O_NOCTTY | O_CLOEXEC | O_NONBLOCK);
    if (channel->fd < 0) return 0;
    if (tcgetattr(channel->fd, &channel->previous)) { close(channel->fd); channel->fd = -1; return 0; }
    struct termios raw = channel->previous;
    raw.c_iflag &= ~(IGNBRK | BRKINT | PARMRK | ISTRIP | INLCR | IGNCR | ICRNL | IXON);
    raw.c_oflag &= ~OPOST; raw.c_lflag &= ~(ECHO | ECHONL | ICANON | ISIG | IEXTEN);
    raw.c_cflag = (raw.c_cflag & ~(CSIZE | PARENB)) | CS8 | CLOCAL | CREAD;
    raw.c_cc[VMIN] = 0; raw.c_cc[VTIME] = 0;
    if (tcsetattr(channel->fd, TCSANOW, &raw)) { close(channel->fd); channel->fd = -1; return 0; }
    return 1;
}
static inline void mpc_channel_close(MPCGuestChannel *channel) {
    if (channel->fd >= 0) { tcsetattr(channel->fd, TCSANOW, &channel->previous); close(channel->fd); channel->fd = -1; }
}
static inline int64_t mpc_channel_millis(void) {
    struct timespec now; if (clock_gettime(CLOCK_MONOTONIC, &now)) return -1;
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}
static inline int mpc_channel_receive(MPCGuestChannel *channel, const MPCReleaseMessage *expected,
                                      MPCReleaseMessage *received, unsigned timeout_ms) {
    unsigned char packet[MPC_RELEASE_WIRE_BYTES]; size_t count = 0;
    int64_t start = mpc_channel_millis(); if (start < 0 || !timeout_ms || timeout_ms > 30000) return 0;
    while (count < sizeof(packet)) {
        int64_t now = mpc_channel_millis(); if (now < start || now - start >= timeout_ms) return 0;
        struct pollfd descriptor = {channel->fd, POLLIN, 0};
        int result = poll(&descriptor, 1, (int)(timeout_ms - (now - start)));
        if (result < 0 && errno == EINTR) continue;
        if (result <= 0 || descriptor.revents & (POLLERR | POLLHUP | POLLNVAL)) return 0;
        if (!(descriptor.revents & POLLIN)) continue;
        ssize_t bytes = read(channel->fd, packet + count, sizeof(packet) - count);
        if (bytes < 0 && (errno == EINTR || errno == EAGAIN)) continue;
        if (bytes <= 0) return 0;
        count += (size_t)bytes;
    }
    return mpc_wire_decode(packet, sizeof(packet), received) && mpc_wire_identity(received, expected);
}
#endif

#import "ProbeBridge.h"
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdio.h>
#include <mutex>
#include <sys/stat.h>

// Save before unsafe execution. No Foundation, allocation or UI in a signal
// handler: recovery happens on next launch from the durable pending marker.
static std::mutex captureLock;
static int traceFD = -1, outputFD = -1, savedOut = -1, savedErr = -1;

static void stopLocked() {
    fflush(stdout); fflush(stderr);
    if (outputFD >= 0) fsync(outputFD);
    if (traceFD >= 0) fsync(traceFD);
    if (savedOut >= 0) { dup2(savedOut, STDOUT_FILENO); close(savedOut); }
    if (savedErr >= 0) { dup2(savedErr, STDERR_FILENO); close(savedErr); }
    if (traceFD >= 0) close(traceFD);
    if (outputFD >= 0) close(outputFD);
    traceFD = outputFD = savedOut = savedErr = -1;
}

BOOL MPCStartDiagnosticCapture(NSString *directory) {
    {
        std::lock_guard<std::mutex> guard(captureLock);
        if (traceFD >= 0 || outputFD >= 0) return NO;
        traceFD = open([directory stringByAppendingPathComponent:@"stages.jsonl"].fileSystemRepresentation,
                       O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0600);
        outputFD = open([directory stringByAppendingPathComponent:@"engine-output.log"].fileSystemRepresentation,
                        O_WRONLY | O_CREAT | O_EXCL | O_APPEND | O_CLOEXEC, 0600);
        if (traceFD < 0 || outputFD < 0) { stopLocked(); return NO; }
        fflush(stdout); fflush(stderr);
        savedOut = fcntl(STDOUT_FILENO, F_DUPFD_CLOEXEC, 3);
        savedErr = fcntl(STDERR_FILENO, F_DUPFD_CLOEXEC, 3);
        if (savedOut < 0 || savedErr < 0 || dup2(outputFD, STDOUT_FILENO) < 0 ||
            dup2(outputFD, STDERR_FILENO) < 0) { stopLocked(); return NO; }
    }
    if (!MPCDiagnosticStage(@"capture-started", @{})) {
        MPCStopDiagnosticCapture(); return NO;
    }
    return YES;
}

BOOL MPCDiagnosticStage(NSString *stage, NSDictionary *details) {
    std::lock_guard<std::mutex> guard(captureLock);
    if (traceFD < 0) return YES; // Optional outside the app's journaled tests.
    NSDictionary *row = @{@"stage": stage, @"unix_seconds": @(NSDate.date.timeIntervalSince1970), @"details": details};
    NSError *error = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:row options:NSJSONWritingSortedKeys error:&error];
    if (!data) return NO;
    NSMutableData *line = [data mutableCopy];
    const char newline = '\n'; [line appendBytes:&newline length:1];
    const auto *bytes = static_cast<const unsigned char *>(line.bytes);
    size_t left = line.length;
    while (left) {
        ssize_t written = write(traceFD, bytes, left);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) return NO;
        bytes += written; left -= static_cast<size_t>(written);
    }
    fflush(stdout); fflush(stderr);
    return fsync(traceFD) == 0 && fsync(outputFD) == 0;
}

void MPCStopDiagnosticCapture(void) {
    std::lock_guard<std::mutex> guard(captureLock);
    stopLocked();
}

NSDictionary *MPCDiagnosticOutputSnapshot(NSString *directory) {
    // The caller supplies its freshly created journal directory. Read a bounded
    // regular-file tail; do not follow a substituted final-component symlink.
    std::lock_guard<std::mutex> guard(captureLock);
    fflush(stdout); fflush(stderr);
    if (outputFD >= 0 && fsync(outputFD) != 0)
        return @{@"status": @"unavailable", @"reason": @"output-flush-failed", @"errno": @(errno)};
    NSString *path = [directory stringByAppendingPathComponent:@"engine-output.log"];
    int fd = open(path.fileSystemRepresentation, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    struct stat info = {};
    if (fd < 0) return @{@"status": @"unavailable", @"errno": @(errno)};
    if (fstat(fd, &info) != 0 || !S_ISREG(info.st_mode) || info.st_size < 0) {
        close(fd); return @{@"status": @"unavailable", @"reason": @"not-readable-regular-file"};
    }
    const off_t limit = 64 * 1024;
    const off_t start = info.st_size > limit ? info.st_size - limit : 0;
    NSMutableData *data = [NSMutableData dataWithLength:static_cast<NSUInteger>(info.st_size - start)];
    size_t total = 0;
    while (total < data.length) {
        ssize_t count = pread(fd, static_cast<unsigned char *>(data.mutableBytes) + total,
                              data.length - total, start + static_cast<off_t>(total));
        if (count < 0 && errno == EINTR) continue;
        if (count <= 0) { close(fd); return @{@"status": @"unavailable", @"reason": @"short-read"}; }
        total += static_cast<size_t>(count);
    }
    close(fd);
    NSString *text = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    NSString *encoding = @"utf8";
    if (!text) { text = [[NSString alloc] initWithData:data encoding:NSISOLatin1StringEncoding]; encoding = @"latin1-fallback"; }
    return @{@"status": @"captured", @"tail": text ?: @"", @"encoding": encoding,
             @"file_bytes": @(info.st_size), @"captured_bytes": @(data.length),
             @"tail_truncated": @(start != 0)};
}

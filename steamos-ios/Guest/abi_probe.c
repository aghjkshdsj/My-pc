#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/futex.h>
#include <linux/reboot.h>
#include <pthread.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/syscall.h>
#include <sys/utsname.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t received;
static _Thread_local uint64_t tls_value;
static int ready;
static int thread_ok;
static void signal_handler(int number) { if (number == SIGUSR1) received = 1; }
static void *worker(void *unused) {
    (void)unused;
    tls_value = 0x12345678;
    thread_ok = tls_value == 0x12345678;
    __atomic_store_n(&ready, 1, __ATOMIC_RELEASE);
    syscall(SYS_futex, &ready, FUTEX_WAKE_PRIVATE, 1, NULL, NULL, 0);
    return NULL;
}
static double milliseconds(clockid_t id) {
    struct timespec ts;
    if (clock_gettime(id, &ts)) return -1;
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1000000.0;
}
static void run_nonce(char out[65]) {
    strcpy(out, "host-smoke");
    FILE *file = fopen("/proc/cmdline", "r");
    if (!file) return;
    char line[4096];
    if (fgets(line, sizeof(line), file)) {
        const char *value = strstr(line, "mpc_run=");
        if (value) {
            value += 8;
            size_t n = 0;
            while (n < 64 && ((value[n] >= 'a' && value[n] <= 'z') || (value[n] >= '0' && value[n] <= '9') || value[n] == '-')) { out[n] = value[n]; ++n; }
            out[n] = 0;
        }
    }
    fclose(file);
}
int main(int argc, char **argv) {
    if (argc > 1 && !strcmp(argv[1], "--exec-child")) return 42;
    setvbuf(stdout, NULL, _IONBF, 0);
    struct utsname info;
    if (uname(&info)) return 1;
    long page = sysconf(_SC_PAGESIZE);
    char nonce[65];
    // /proc is mounted only by the tiny initramfs init script, not by this binary.
    run_nonce(nonce);
    int failures = 0;
    struct sigaction action = {.sa_handler = signal_handler};
    sigemptyset(&action.sa_mask);
    int signals = sigaction(SIGUSR1, &action, NULL) == 0 && raise(SIGUSR1) == 0 && received;
    failures += !signals;
    unsigned char *memory = mmap(NULL, (size_t)page * 2, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    int mapping = memory != MAP_FAILED;
    if (mapping) {
        memory[0] = 17; memory[page] = 31;
        mapping = mprotect(memory, (size_t)page, PROT_READ) == 0 && memory[0] == 17 && memory[page] == 31;
        mapping = munmap(memory, (size_t)page * 2) == 0 && mapping;
    }
    failures += !mapping;
    tls_value = 0xabcdef;
    pthread_t thread;
    int threads = pthread_create(&thread, NULL, worker, NULL) == 0;
    if (threads) {
        while (!__atomic_load_n(&ready, __ATOMIC_ACQUIRE)) {
            int result = (int)syscall(SYS_futex, &ready, FUTEX_WAIT_PRIVATE, 0, NULL, NULL, 0);
            if (result < 0 && errno != EAGAIN && errno != EINTR) { threads = 0; break; }
        }
        threads = pthread_join(thread, NULL) == 0 && threads && thread_ok && tls_value == 0xabcdef;
    }
    failures += !threads;
    pid_t child = fork();
    if (child == 0) { execl(argv[0], argv[0], "--exec-child", (char *)NULL); _exit(99); }
    int status = 0;
    int process = child > 0 && waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 42;
    failures += !process;
    uint64_t value = 1;
    double wall_start = milliseconds(CLOCK_MONOTONIC), cpu_start = milliseconds(CLOCK_PROCESS_CPUTIME_ID);
    for (int i = 0; i < 1000000; ++i) { value ^= value >> 12; value ^= value << 25; value ^= value >> 27; value *= UINT64_C(2685821657736338717); }
    double cpu_ms = milliseconds(CLOCK_PROCESS_CPUTIME_ID) - cpu_start;
    double wall_ms = milliseconds(CLOCK_MONOTONIC) - wall_start;
    failures += value != UINT64_C(0x1d250c45a7bbc87e);
#if defined(__aarch64__)
    const char *elf = "aarch64";
#elif defined(__x86_64__)
    const char *elf = "x86_64";
#else
    const char *elf = "other";
#endif
    printf("MPC_LINUX_ABI {\"schema\":1,\"run\":\"%s\",\"kernel\":\"%s\",\"machine\":\"%s\",\"elf_arch\":\"%s\",\"page_bytes\":%ld,\"signals\":%s,\"mmap_protection\":%s,\"pthread_tls_futex\":%s,\"fork_exec\":%s,\"checksum\":\"%016llx\",\"cpu_ms\":%.6f,\"wall_ms\":%.6f,\"failures\":%d}\n",
           nonce, info.release, info.machine, elf, page, signals ? "true":"false", mapping ? "true":"false", threads ? "true":"false", process ? "true":"false", (unsigned long long)value, cpu_ms, wall_ms, failures);
    return failures ? 1 : 0;
}

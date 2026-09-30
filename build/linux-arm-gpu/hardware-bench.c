/* My-pc diagnostic workload. Built unchanged for AArch64 and x86-64.
 * This is application test code, not a modification of FEX or Mesa. */
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <pthread.h>
#include <dlfcn.h>

#if defined(__x86_64__)
#define ARCH "x86_64"
#elif defined(__aarch64__)
#define ARCH "aarch64"
#else
#error Unsupported diagnostic architecture
#endif

static double now(clockid_t clock) {
    struct timespec t;
    if (clock_gettime(clock, &t)) exit(2);
    return t.tv_sec + t.tv_nsec / 1e9;
}

/* Dependent integer operations prevent vectorization or dead-code removal.
 * Each worker has the same fixed work; throughput is iterations/wall second. */
static uint64_t workload(uint64_t seed, uint64_t iterations) {
    for (uint64_t i = 0; i < iterations; ++i) {
        seed ^= seed >> 12; seed ^= seed << 25; seed ^= seed >> 27;
        seed *= UINT64_C(2685821657736338717);
    }
    return seed;
}

struct worker { uint64_t seed, iterations, result; };
static void *run_worker(void *arg) {
    struct worker *w = arg;
    w->result = workload(w->seed, w->iterations);
    return NULL;
}

static int cpu(int workers, uint64_t iterations) {
    if (workers < 1 || workers > 64 || iterations < 1 || iterations > 1000000) return 2;
    struct worker work[64]; pthread_t threads[64];
    /* Warm the loop in this process before timing steady-state work. */
    volatile uint64_t warm = workload(1, 5000); (void)warm;
    for (int sample = 0; sample < 3; ++sample) {
        double start = now(CLOCK_MONOTONIC), cpustart = now(CLOCK_PROCESS_CPUTIME_ID);
        for (int i = 0; i < workers; ++i) {
            work[i] = (struct worker){(uint64_t)i + 1, iterations, 0};
            if (workers == 1) run_worker(&work[i]);
            else if (pthread_create(&threads[i], NULL, run_worker, &work[i])) return 3;
        }
        if (workers > 1) for (int i = 0; i < workers; ++i)
            if (pthread_join(threads[i], NULL)) return 3;
        double seconds = now(CLOCK_MONOTONIC) - start;
        double cpuseconds = now(CLOCK_PROCESS_CPUTIME_ID) - cpustart;
        uint64_t checksum = 0;
        for (int i = 0; i < workers; ++i) checksum ^= work[i].result;
        printf("MYPC_BENCH {\"kind\":\"cpu\",\"arch\":\"%s\",\"workers\":%d,"
               "\"iterations_per_worker\":%llu,\"wall_ms\":%.4f,\"process_cpu_ms\":%.4f,"
               "\"million_iterations_s\":%.4f,\"checksum\":\"%016llx\"}\n",
               ARCH, workers, (unsigned long long)iterations, seconds * 1000,
               cpuseconds * 1000, iterations * workers / seconds / 1e6,
               (unsigned long long)checksum);
        fflush(stdout);
    }
    return 0;
}

/* Load graphics dynamically so CPU tests work independently of graphics.
 * FEX uses the separate test root's unchanged EGL/GL forwarding libraries. */
typedef void *Display; typedef unsigned long Window;
typedef void *EDisplay; typedef void *Config; typedef void *Surface; typedef void *Context;
typedef unsigned int U; typedef int I; typedef float F;
#define DECL(ret, name, ...) static ret (*name)(__VA_ARGS__)
DECL(Display *, XOpenDisplay, const char *);
DECL(Window, XDefaultRootWindow, Display *);
DECL(void *, XDefaultVisual, Display *, int);
DECL(int, XDefaultScreen, Display *);
DECL(unsigned long, XVisualIDFromVisual, void *);
DECL(Window, XCreateSimpleWindow, Display *, Window, int, int, unsigned int, unsigned int,
     unsigned int, unsigned long, unsigned long);
DECL(int, XStoreName, Display *, Window, const char *);
DECL(int, XMapWindow, Display *, Window);
DECL(int, XSync, Display *, int);
DECL(int, XDestroyWindow, Display *, Window);
DECL(int, XCloseDisplay, Display *);
DECL(EDisplay, eglGetDisplay, void *);
DECL(U, eglInitialize, EDisplay, I *, I *);
DECL(U, eglBindAPI, U);
DECL(U, eglChooseConfig, EDisplay, const I *, Config *, I, I *);
DECL(U, eglGetConfigAttrib, EDisplay, Config, I, I *);
DECL(Surface, eglCreateWindowSurface, EDisplay, Config, Window, const I *);
DECL(Context, eglCreateContext, EDisplay, Config, Context, const I *);
DECL(U, eglMakeCurrent, EDisplay, Surface, Surface, Context);
DECL(U, eglSwapInterval, EDisplay, I);
DECL(U, eglSwapBuffers, EDisplay, Surface);
DECL(U, eglDestroyContext, EDisplay, Context);
DECL(U, eglDestroySurface, EDisplay, Surface);
DECL(U, eglTerminate, EDisplay);
DECL(void *, eglGetProcAddress, const char *);
DECL(const unsigned char *, glGetString, U);
DECL(U, glCreateShader, U);
DECL(void, glShaderSource, U, I, const char *const *, const I *);
DECL(void, glCompileShader, U);
DECL(void, glGetShaderiv, U, U, I *);
DECL(void, glDeleteShader, U);
DECL(U, glCreateProgram, void);
DECL(void, glAttachShader, U, U);
DECL(void, glBindAttribLocation, U, U, const char *);
DECL(void, glLinkProgram, U);
DECL(void, glGetProgramiv, U, U, I *);
DECL(void, glUseProgram, U);
DECL(void, glDeleteProgram, U);
DECL(I, glGetUniformLocation, U, const char *);
DECL(void, glUniform4f, I, F, F, F, F);
DECL(void, glViewport, I, I, I, I);
DECL(void, glVertexAttribPointer, U, I, U, unsigned char, I, const void *);
DECL(void, glEnableVertexAttribArray, U);
DECL(void, glDrawArrays, U, I, I);
DECL(void, glReadPixels, I, I, I, I, U, U, void *);
DECL(void, glFinish, void);
DECL(U, glGetError, void);
#define LOAD(lib, name) do { *(void **)(&name) = dlsym(lib, #name); if (!name) goto failed; } while (0)
#define GL(name) do { *(void **)(&name) = eglGetProcAddress(#name); if (!name) goto failed; } while (0)

static U shader(U type, const char *source) {
    U handle = glCreateShader(type); I okay = 0;
    glShaderSource(handle, 1, &source, NULL); glCompileShader(handle);
    glGetShaderiv(handle, 0x8B81, &okay);
    if (!okay) { glDeleteShader(handle); return 0; }
    return handle;
}
static int compare_double(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static int gpu(void) {
    const char *stage = "libraries";
    void *x11 = dlopen("libX11.so.6", RTLD_NOW | RTLD_LOCAL);
    void *egl = dlopen("libEGL.so.1", RTLD_NOW | RTLD_LOCAL);
    Display *display = NULL; EDisplay ed = NULL;
    Window window = 0; Surface surface = NULL; Context context = NULL;
    U program = 0, vertex = 0, fragment = 0;
    int status = 4;
    if (!x11 || !egl) goto failed;
    LOAD(x11, XOpenDisplay); LOAD(x11, XDefaultRootWindow); LOAD(x11, XDefaultScreen);
    LOAD(x11, XDefaultVisual); LOAD(x11, XVisualIDFromVisual); LOAD(x11, XCreateSimpleWindow);
    LOAD(x11, XStoreName); LOAD(x11, XMapWindow); LOAD(x11, XSync);
    LOAD(x11, XDestroyWindow); LOAD(x11, XCloseDisplay);
    LOAD(egl, eglGetDisplay); LOAD(egl, eglInitialize); LOAD(egl, eglBindAPI);
    LOAD(egl, eglChooseConfig); LOAD(egl, eglGetConfigAttrib); LOAD(egl, eglCreateWindowSurface);
    LOAD(egl, eglCreateContext); LOAD(egl, eglMakeCurrent); LOAD(egl, eglSwapInterval);
    LOAD(egl, eglSwapBuffers); LOAD(egl, eglDestroyContext); LOAD(egl, eglDestroySurface);
    LOAD(egl, eglTerminate); LOAD(egl, eglGetProcAddress);
    stage = "X11"; display = XOpenDisplay(NULL); if (!display) goto failed;
    stage = "EGL"; ed = eglGetDisplay(display);
    if (!ed || !eglInitialize(ed, NULL, NULL) || !eglBindAPI(0x30A0)) goto failed;
    /* EGL window / ES2 / RGB8, same visual as the X11 default window. */
    I attributes[] = {0x3033, 4, 0x3040, 4, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3038};
    Config configs[64], config = NULL; I count = 0;
    if (!eglChooseConfig(ed, attributes, configs, 64, &count)) goto failed;
    unsigned long visual = XVisualIDFromVisual(XDefaultVisual(display, XDefaultScreen(display)));
    for (I i = 0; i < count; ++i) {
        I id = 0; if (eglGetConfigAttrib(ed, configs[i], 0x302E, &id) && (unsigned long)id == visual)
            { config = configs[i]; break; }
    }
    stage = "window"; if (!config) goto failed;
    window = XCreateSimpleWindow(display, XDefaultRootWindow(display), 40, 40, 800, 500, 0, 0, 0);
    XStoreName(display, window, "My-pc GPU test: " ARCH); XMapWindow(display, window); XSync(display, 0);
    surface = eglCreateWindowSurface(ed, config, window, NULL);
    I context_args[] = {0x3098, 2, 0x3038};
    context = eglCreateContext(ed, config, NULL, context_args);
    stage = "context";
    if (!surface || !context || !eglMakeCurrent(ed, surface, surface, context)) goto failed;
    eglSwapInterval(ed, 0);
    GL(glGetString); GL(glCreateShader); GL(glShaderSource); GL(glCompileShader); GL(glGetShaderiv);
    GL(glDeleteShader); GL(glCreateProgram); GL(glAttachShader); GL(glBindAttribLocation);
    GL(glLinkProgram); GL(glGetProgramiv); GL(glUseProgram); GL(glDeleteProgram);
    GL(glGetUniformLocation); GL(glUniform4f); GL(glViewport); GL(glVertexAttribPointer);
    GL(glEnableVertexAttribArray); GL(glDrawArrays); GL(glReadPixels); GL(glFinish); GL(glGetError);
    stage = "shader";
    vertex = shader(0x8B31, "attribute vec2 position; void main(){gl_Position=vec4(position,0.,1.);}");
    fragment = shader(0x8B30, "precision mediump float; uniform vec4 tint; void main(){gl_FragColor=tint;}");
    if (!vertex || !fragment) goto failed;
    program = glCreateProgram(); glAttachShader(program, vertex); glAttachShader(program, fragment);
    glBindAttribLocation(program, 0, "position"); glLinkProgram(program);
    I okay = 0; glGetProgramiv(program, 0x8B82, &okay); if (!okay) goto failed;
    glUseProgram(program); I tint = glGetUniformLocation(program, "tint");
    F vertices[] = {-1,-1, 3,-1, -1,3};
    glViewport(0, 0, 800, 500); glVertexAttribPointer(0, 2, 0x1406, 0, 0, vertices);
    glEnableVertexAttribArray(0);
    unsigned char pixel[4] = {0};
    stage = "pixel";
    /* A real shader draw and exact red/green/blue readbacks, not just a name. */
    for (int color = 0; color < 3; ++color) {
        glUniform4f(tint, color == 0, color == 1, color == 2, 1);
        glDrawArrays(4, 0, 3); glReadPixels(400, 250, 1, 1, 0x1908, 0x1401, pixel);
        if (glGetError() || pixel[color] != 255 || pixel[(color+1)%3] || pixel[(color+2)%3]) goto failed;
        if (!eglSwapBuffers(ed, surface)) goto failed;
    }
    const unsigned char *renderer = glGetString(0x1F01), *version = glGetString(0x1F02);
    /* Restrict strings to printable JSON-safe characters. */
    char name[257] = {0}, ver[129] = {0};
    for (int i = 0; i < 256 && renderer && renderer[i]; ++i)
        name[i] = renderer[i] >= 32 && renderer[i] < 127 && renderer[i] != '"' && renderer[i] != '\\' ? renderer[i] : '?';
    for (int i = 0; i < 128 && version && version[i]; ++i)
        ver[i] = version[i] >= 32 && version[i] < 127 && version[i] != '"' && version[i] != '\\' ? version[i] : '?';
    double drawtime[60], finishtime[60], swaptime[60];
    /* Warm shaders, then 60 visible frames, 16 full-screen draws per frame.
     * Finish separates CPU submission from GPU completion/backpressure.
     * This is a deliberately synchronized test, not an in-game FPS estimate. */
    stage = "frames"; double start = now(CLOCK_MONOTONIC);
    for (int frame = 0; frame < 60; ++frame) {
        double a = now(CLOCK_MONOTONIC);
        for (int draw = 0; draw < 16; ++draw) {
            glUniform4f(tint, (frame % 20) / 19.f, (draw % 8) / 7.f, (frame % 3) / 2.f, 1);
            glDrawArrays(4, 0, 3);
        }
        double b = now(CLOCK_MONOTONIC); glFinish(); double c = now(CLOCK_MONOTONIC);
        if (!eglSwapBuffers(ed, surface) || glGetError()) goto failed;
        double d = now(CLOCK_MONOTONIC);
        drawtime[frame] = (b-a)*1000; finishtime[frame] = (c-b)*1000; swaptime[frame] = (d-c)*1000;
    }
    double seconds = now(CLOCK_MONOTONIC) - start;
    qsort(drawtime, 60, sizeof(double), compare_double);
    qsort(finishtime, 60, sizeof(double), compare_double);
    qsort(swaptime, 60, sizeof(double), compare_double);
    printf("MYPC_BENCH {\"kind\":\"gpu\",\"arch\":\"%s\",\"renderer\":\"%s\",\"version\":\"%s\","
           "\"readback_ok\":true,\"frames\":60,\"width\":800,\"height\":500,\"draws_per_frame\":16,"
           "\"wall_ms\":%.4f,\"render_fps\":%.4f,\"submit_median_ms\":%.4f,\"submit_p95_ms\":%.4f,"
           "\"finish_median_ms\":%.4f,\"finish_p95_ms\":%.4f,\"swap_median_ms\":%.4f,\"swap_p95_ms\":%.4f}\n",
           ARCH, name, ver, seconds*1000, 60/seconds,
           drawtime[30], drawtime[56], finishtime[30], finishtime[56], swaptime[30], swaptime[56]);
    fflush(stdout); status = 0;
failed:
    if (status) fprintf(stderr, "MYPC_BENCH_FAILED stage=%s\n", stage);
    if (program && glDeleteProgram) glDeleteProgram(program);
    if (vertex && glDeleteShader) glDeleteShader(vertex);
    if (fragment && glDeleteShader) glDeleteShader(fragment);
    if (ed && eglMakeCurrent) eglMakeCurrent(ed, NULL, NULL, NULL);
    if (context && eglDestroyContext) eglDestroyContext(ed, context);
    if (surface && eglDestroySurface) eglDestroySurface(ed, surface);
    if (ed && eglTerminate) eglTerminate(ed);
    if (window && XDestroyWindow) XDestroyWindow(display, window);
    if (display && XCloseDisplay) XCloseDisplay(display);
    if (egl) dlclose(egl); if (x11) dlclose(x11);
    return status;
}

int main(int argc, char **argv) {
    if (argc == 4 && !strcmp(argv[1], "cpu")) return cpu(atoi(argv[2]), strtoull(argv[3], NULL, 10));
    if (argc == 2 && !strcmp(argv[1], "gpu")) return gpu();
    fprintf(stderr, "Usage: hardware-bench cpu WORKERS ITERATIONS | gpu\n"); return 2;
}

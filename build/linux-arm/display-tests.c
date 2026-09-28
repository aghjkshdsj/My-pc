/* Exercise the actual bridge's frame scheduling without booting a guest. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

typedef struct { int width, height; uint32_t pixel; } pixman_image_t;
typedef struct { pixman_image_t *image; } DisplaySurface;
typedef struct DisplayChangeListener DisplayChangeListener;
typedef struct {
    const char *dpy_name;
    void (*dpy_refresh)(DisplayChangeListener *);
    void (*dpy_gfx_update)(DisplayChangeListener *, int, int, int, int);
    void (*dpy_gfx_switch)(DisplayChangeListener *, DisplaySurface *);
} DisplayChangeListenerOps;
struct DisplayChangeListener { const DisplayChangeListenerOps *ops; void *con; };
#define PIXMAN_OP_SRC 0
#define PIXMAN_a8r8g8b8 0
static int copies, frames, interval;
static pixman_image_t screen = {960, 540, 0xff223344};
static DisplaySurface surface = {&screen};
static int surface_width(DisplaySurface *s) { return s->image->width; }
static int surface_height(DisplaySurface *s) { return s->image->height; }
static pixman_image_t *pixman_image_create_bits(int format, int w, int h, void *p, int stride) {
    pixman_image_t *result = calloc(1, sizeof(*result));
    assert(result); result->width = w; result->height = h; return result;
}
static void pixman_image_unref(pixman_image_t *p) { free(p); }
static void pixman_image_composite32(int op, pixman_image_t *src, void *mask,
                                     pixman_image_t *dst, int sx, int sy, int mx,
                                     int my, int dx, int dy, int w, int h) {
    copies++; dst->pixel = src->pixel;
}
static void *pixman_image_get_data(pixman_image_t *p) { return &p->pixel; }
static int pixman_image_get_stride(pixman_image_t *p) { return p->width * 4; }
static void *qemu_console_lookup_by_index(int i) { return &surface; }
static void graphic_hw_update(void *con) { }
static void register_displaychangelistener(DisplayChangeListener *d) { d->ops->dpy_gfx_switch(d, &surface); }
static void unregister_displaychangelistener(DisplayChangeListener *d) { }
static void update_displaychangelistener(DisplayChangeListener *d, int ms) { interval = ms; }

#include "qemu-display.inc.c"

static void receive(void *opaque, const void *pixels, int width, int height, int stride) {
    assert(*(const uint32_t *)pixels == screen.pixel);
    assert(width == screen.width && height == screen.height && stride == width * 4);
    frames++;
}
int main(void) {
    assert(my_pc_display_start(receive, NULL) == 0 && interval == 33);
    assert(my_pc_display_start(receive, NULL) == -1);
    DisplayChangeListener *d = &my_pc_display_listener;
    for (int i = 0; i < 1000; ++i) d->ops->dpy_gfx_update(d, 0, 0, 1, 1);
    assert(frames == 0 && copies == 0);
    d->ops->dpy_refresh(d);
    assert(frames == 1 && copies == 1);
    for (int i = 0; i < 10; ++i) d->ops->dpy_refresh(d);
    assert(frames == 1 && copies == 1); /* No repeated copies of an idle screen. */
    screen.pixel = 0xffabcdef;
    d->ops->dpy_gfx_update(d, 2, 3, 1, 1);
    d->ops->dpy_refresh(d);
    assert(frames == 2 && copies == 2);
    screen.width = 1280;
    d->ops->dpy_gfx_switch(d, &surface);
    d->ops->dpy_refresh(d);
    assert(frames == 3 && copies == 3);
    my_pc_display_stop();
    d->ops->dpy_refresh(d);
    assert(frames == 3 && copies == 3);
    puts("PASS: batched dirty frames, idle display, resized surface, stopped display");
}

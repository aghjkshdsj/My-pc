/* My-pc software display bridge, GPL-3.0-or-later.
 * Included in QEMU ui/console.c by our pinned build. All callbacks execute on
 * QEMU's main loop under its display lock. Consumers must copy before returning.
 * This is a bring-up framebuffer path, not GPU acceleration.
 */
typedef void (*MyPCFrameCallback)(void *, const void *, int, int, int);
static MyPCFrameCallback my_pc_frame_callback;
static void *my_pc_frame_opaque;
static DisplaySurface *my_pc_surface;
static pixman_image_t *my_pc_pixels;
static bool my_pc_display_registered;
static bool my_pc_frame_dirty;

static void my_pc_frame_update(DisplayChangeListener *dcl, int x, int y, int w, int h)
{
    /* A guest repaint can issue hundreds of small dirty rectangles. Copying
     * the whole screen for each one wastes CPU and memory bandwidth. */
    my_pc_frame_dirty = true;
}

static void my_pc_frame_switch(DisplayChangeListener *dcl, DisplaySurface *surface)
{
    if (my_pc_pixels) {
        pixman_image_unref(my_pc_pixels);
        my_pc_pixels = NULL;
    }
    my_pc_surface = surface;
    my_pc_frame_dirty = true;
    int width = surface_width(surface);
    int height = surface_height(surface);
    if (width > 0 && height > 0 && width <= 4096 && height <= 4096) {
        my_pc_pixels = pixman_image_create_bits(PIXMAN_a8r8g8b8,
                                               width, height, NULL, 0);
    }
}

static void my_pc_frame_refresh(DisplayChangeListener *dcl)
{
    graphic_hw_update(dcl->con);
    if (!my_pc_frame_dirty || !my_pc_frame_callback || !my_pc_surface || !my_pc_pixels) {
        return;
    }
    my_pc_frame_dirty = false;
    int width = surface_width(my_pc_surface);
    int height = surface_height(my_pc_surface);
    pixman_image_composite32(PIXMAN_OP_SRC, my_pc_surface->image, NULL,
                            my_pc_pixels, 0, 0, 0, 0, 0, 0, width, height);
    my_pc_frame_callback(my_pc_frame_opaque, pixman_image_get_data(my_pc_pixels),
                        width, height, pixman_image_get_stride(my_pc_pixels));
}

static const DisplayChangeListenerOps my_pc_display_ops = {
    .dpy_name = "my-pc-framebuffer",
    .dpy_refresh = my_pc_frame_refresh,
    .dpy_gfx_update = my_pc_frame_update,
    .dpy_gfx_switch = my_pc_frame_switch,
};
static DisplayChangeListener my_pc_display_listener;

__attribute__((visibility("default")))
int my_pc_display_start(MyPCFrameCallback callback, void *opaque)
{
    if (my_pc_display_registered || !callback) {
        return -1;
    }
    my_pc_frame_callback = callback;
    my_pc_frame_opaque = opaque;
    my_pc_display_listener.ops = &my_pc_display_ops;
    my_pc_display_listener.con = qemu_console_lookup_by_index(0);
    if (!my_pc_display_listener.con) {
        my_pc_frame_callback = NULL;
        return -1;
    }
    register_displaychangelistener(&my_pc_display_listener);
    update_displaychangelistener(&my_pc_display_listener, 33);
    my_pc_display_registered = true;
    return 0;
}

__attribute__((visibility("default")))
void my_pc_display_stop(void)
{
    if (my_pc_display_registered) {
        unregister_displaychangelistener(&my_pc_display_listener);
    }
    my_pc_display_registered = false;
    my_pc_frame_callback = NULL;
    my_pc_frame_opaque = NULL;
    my_pc_surface = NULL;
    my_pc_frame_dirty = false;
    if (my_pc_pixels) {
        pixman_image_unref(my_pc_pixels);
        my_pc_pixels = NULL;
    }
}

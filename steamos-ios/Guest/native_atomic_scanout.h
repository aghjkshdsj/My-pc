/* SPDX-License-Identifier: MIT
 * Standard DRM completion control for GPU-produced exported images. Included
 * by the separate generated eight-frame producer, never the old diagnostic. */
#ifndef MPC_NATIVE_ATOMIC_SCANOUT_H
#define MPC_NATIVE_ATOMIC_SCANOUT_H
#include <limits.h>
#include <poll.h>
#include <sys/ioctl.h>
#include <linux/sync_file.h>
typedef struct MPCNativeAtomicOutput {
    uint32_t plane, blob, connector_crtc, active, mode, output;
    uint32_t fb, crtc, sx, sy, sw, sh, cx, cy, cw, ch;
    unsigned events, frames, positive, expected_events;
    int unexpected, initialized;
} MPCNativeAtomicOutput;
static MPCNativeAtomicOutput native_atomic;
static uint32_t native_property(uint32_t object,uint32_t type,const char *name,uint64_t *value)
{
    drmModeObjectProperties *props=drmModeObjectGetProperties(scanout_fd,object,type);
    uint32_t found=0;
    if(props && props->count_props<=256) for(uint32_t i=0;i<props->count_props;i++) {
        drmModePropertyRes *p=drmModeGetProperty(scanout_fd,props->props[i]);
        if(!p)continue;
        if(!strcmp(p->name,name)) { found=p->prop_id;if(value)*value=props->prop_values[i]; }
        drmModeFreeProperty(p);if(found)break;
    }
    if(props)drmModeFreeObjectProperties(props);return found;
}
static int native_prepare(void)
{
    if(drmSetClientCap(scanout_fd,DRM_CLIENT_CAP_UNIVERSAL_PLANES,1) ||
       drmSetClientCap(scanout_fd,DRM_CLIENT_CAP_ATOMIC,1))return -1;
    drmModeRes *r=drmModeGetResources(scanout_fd);unsigned index=32;
    if(r && r->count_crtcs<=32)for(int i=0;i<r->count_crtcs;i++)if(r->crtcs[i]==scanout_crtc)index=(unsigned)i;
    if(r)drmModeFreeResources(r);if(index>=32)return -1;
    drmModePlaneRes *planes=drmModeGetPlaneResources(scanout_fd);
    if(planes && planes->count_planes<=64)for(uint32_t i=0;i<planes->count_planes && !native_atomic.plane;i++) {
        drmModePlane *p=drmModeGetPlane(scanout_fd,planes->planes[i]);uint64_t type=UINT64_MAX;int format=0;
        if(!p)continue;
        if(p->count_formats<=256)for(uint32_t j=0;j<p->count_formats;j++)format|=p->formats[j]==DRM_FORMAT_XRGB8888;
        if((p->possible_crtcs&(1u<<index)) && format &&
            native_property(p->plane_id,DRM_MODE_OBJECT_PLANE,"type",&type) && type==DRM_PLANE_TYPE_PRIMARY)
            native_atomic.plane=p->plane_id;
        drmModeFreePlane(p);
    }
    if(planes)drmModeFreePlaneResources(planes);if(!native_atomic.plane)return -1;
#define NP(field,obj,type,name) native_atomic.field=native_property(obj,type,name,NULL);if(!native_atomic.field)return -1
    NP(connector_crtc,scanout_connector,DRM_MODE_OBJECT_CONNECTOR,"CRTC_ID");
    NP(active,scanout_crtc,DRM_MODE_OBJECT_CRTC,"ACTIVE");
    NP(mode,scanout_crtc,DRM_MODE_OBJECT_CRTC,"MODE_ID");
    NP(output,scanout_crtc,DRM_MODE_OBJECT_CRTC,"OUT_FENCE_PTR");
    NP(fb,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"FB_ID");
    NP(crtc,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"CRTC_ID");
    NP(sx,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"SRC_X");
    NP(sy,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"SRC_Y");
    NP(sw,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"SRC_W");
    NP(sh,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"SRC_H");
    NP(cx,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"CRTC_X");
    NP(cy,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"CRTC_Y");
    NP(cw,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"CRTC_W");
    NP(ch,native_atomic.plane,DRM_MODE_OBJECT_PLANE,"CRTC_H");
#undef NP
    if(drmModeCreatePropertyBlob(scanout_fd,&scanout_mode,sizeof(scanout_mode),&native_atomic.blob))return -1;
    native_atomic.initialized=1;return 0;
}
static int native_commit(uint32_t framebuffer,uint32_t flags,int *fence,int disable)
{
    drmModeAtomicReq *request=drmModeAtomicAlloc();if(!request)return -1;int ok=1;
#define NA(obj,prop,val) do {if(drmModeAtomicAddProperty(request,obj,native_atomic.prop,val)<0)ok=0;}while(0)
    NA(scanout_connector,connector_crtc,disable?0:scanout_crtc);
    NA(scanout_crtc,active,disable?0:1);NA(scanout_crtc,mode,disable?0:native_atomic.blob);
    NA(native_atomic.plane,fb,disable?0:framebuffer);NA(native_atomic.plane,crtc,disable?0:scanout_crtc);
    if(!disable) {
        NA(native_atomic.plane,sx,0);NA(native_atomic.plane,sy,0);
        NA(native_atomic.plane,sw,(uint64_t)WIDTH<<16);NA(native_atomic.plane,sh,(uint64_t)HEIGHT<<16);
        NA(native_atomic.plane,cx,0);NA(native_atomic.plane,cy,0);
        NA(native_atomic.plane,cw,WIDTH);NA(native_atomic.plane,ch,HEIGHT);
    }
    if(fence)NA(scanout_crtc,output,(uintptr_t)fence);
#undef NA
    int result=ok?drmModeAtomicCommit(scanout_fd,request,flags,&native_atomic):-1;
    drmModeAtomicFree(request);return result;
}
static void native_event(int fd,unsigned sequence,unsigned sec,unsigned usec,unsigned crtc,void *data)
{
    (void)fd;(void)sequence;(void)sec;(void)usec;
    if(data!=&native_atomic || crtc!=scanout_crtc)native_atomic.unexpected=1;
    native_atomic.events++;
}
static int native_status(int fence)
{
    struct sync_file_info info={0};
    if(ioctl(fence,SYNC_IOC_FILE_INFO,&info) || !info.num_fences)return INT_MIN;
    return info.status;
}
static int native_hold(const char *reason)
{
    printf("MPC_NATIVE_KMS_HELD {\"schema\":1,\"run\":\"%s\",\"reason\":\"%s\","
        "\"buffers_retained\":true,\"cleanup_completed\":false}\n",image_run,reason);fflush(stdout);
    /* CPU timeout/query failure cannot authorize Vulkan/GEM free or recycling. */
    for(;;)pause();
    return -1;
}
static int native_present(uint32_t framebuffer,unsigned pass)
{
    if(!native_atomic.initialized && native_prepare())return image_reject("native-atomic-properties",errno);
    if(!pass && native_commit(framebuffer,DRM_MODE_ATOMIC_TEST_ONLY|DRM_MODE_ATOMIC_ALLOW_MODESET,NULL,0))
        return image_reject("native-atomic-test-only",errno);
    int fence=-1;uint32_t flags=pass?DRM_MODE_ATOMIC_NONBLOCK|DRM_MODE_PAGE_FLIP_EVENT:DRM_MODE_ATOMIC_ALLOW_MODESET;
    native_atomic.events=0;native_atomic.expected_events=pass?1:0;
    if(native_commit(framebuffer,flags,&fence,0) || fence<0)return native_hold("submit-or-output-fence");
    int status=0;
    for(unsigned attempts=0;attempts<100;attempts++) {
        status=native_status(fence);
        if(status==INT_MIN || native_atomic.unexpected || native_atomic.events>native_atomic.expected_events)
            return native_hold("invalid-fence-or-event");
        if(status && native_atomic.events==native_atomic.expected_events)break;
        struct pollfd pollfds[2]={{fence,status?0:POLLIN,0},{scanout_fd,POLLIN,0}};
        int ready=poll(pollfds,2,100);
        if(ready<0 && errno==EINTR){attempts--;continue;}
        if(ready<0)return native_hold("poll-error");
        if(pollfds[1].revents&POLLIN) {
            drmEventContext context={.version=3,.page_flip_handler2=native_event};
            if(drmHandleEvent(scanout_fd,&context))return native_hold("event-read-error");
        }
    }
    if(!status || native_atomic.events!=native_atomic.expected_events)return native_hold("missing-terminal-or-event");
    close(fence);
    if(status!=1)return image_reject("native-display-fence-error",status);
    native_atomic.frames++;native_atomic.positive++;
    printf("MPC_NATIVE_KMS_FLIP {\"schema\":1,\"run\":\"%s\",\"index\":%u,\"framebuffer\":%u,"
        "\"crtc\":%u,\"event_count\":%u,\"output_fence_status\":1,\"uart_release_used\":false}\n",
        image_run,pass,framebuffer,scanout_crtc,native_atomic.events);fflush(stdout);return 0;
}
static int native_disable(void)
{
    if(native_atomic.frames!=MPC_SCANOUT_FRAME_COUNT || native_atomic.positive!=MPC_SCANOUT_FRAME_COUNT)
        return native_hold("incomplete-frame-ownership");
    /* Every prior frame's native readers are already terminal before disable. */
    if(native_commit(0,DRM_MODE_ATOMIC_ALLOW_MODESET,NULL,1))return native_hold("disable-rejected");
    if(drmModeDestroyPropertyBlob(scanout_fd,native_atomic.blob))return image_reject("native-mode-blob-cleanup",errno);
    return 0;
}
#endif

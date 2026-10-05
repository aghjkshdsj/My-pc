/* Fresh Linux image export/KMS diagnostic, MIT. No host-generated pixels. */
#ifndef MPC_MOVING_SCANOUT_H
#define MPC_MOVING_SCANOUT_H
#include <errno.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <xf86drm.h>
#include <xf86drmMode.h>
#include <drm_fourcc.h>
#include <virtgpu_drm.h>
#include "image_export_contract.h"
#include "image_framebuffer.h"
#include "frame_release_channel.h"
#include "../Engine/MovingFrameContract.h"

#ifndef MPC_SCANOUT_FRAME_COUNT
#define MPC_SCANOUT_FRAME_COUNT MPC_MOVING_BUFFERS
#endif
#ifndef MPC_SCANOUT_PREFIX
#define MPC_SCANOUT_PREFIX "MPC_MOVE"
#endif
#ifndef MPC_SCANOUT_NONCE_ENV
#define MPC_SCANOUT_NONCE_ENV MPC_SCANOUT_PREFIX "_RUN"
#endif
#ifndef MPC_SCANOUT_WAIT_NS
#define MPC_SCANOUT_WAIT_NS 2000000000UL
#endif
#if MPC_SCANOUT_FRAME_COUNT != MPC_MOVING_BUFFERS
#error "The moving gate requires exactly three buffers"
#endif

typedef struct MPCImageExport {
    VkImage image;
    VkDeviceMemory memory;
    VkSubresourceLayout layout;
    VkDeviceSize allocation;
    uint32_t framebuffer, gem_handle, resource;
    int exported_fd;
} MPCImageExport;
static MPCImageExport exported_images[MPC_SCANOUT_FRAME_COUNT];
static int scanout_fd = -1;
static uint32_t scanout_connector, scanout_crtc;
static drmModeModeInfo scanout_mode;
static const char *image_run;
static MPCGuestChannel moving_channel = {.fd = -1};
static uint64_t moving_high, moving_low, moving_registry, moving_submission;
static uint64_t moving_serial[MPC_MOVING_BUFFERS], moving_release[MPC_MOVING_BUFFERS];
static int moving_owned[MPC_MOVING_BUFFERS];
static int moving_register(VkDevice device, unsigned slot);
static MPCReleaseMessage moving_expected(unsigned slot, unsigned kind, uint64_t serial, uint64_t release) {
    MPCReleaseMessage result = {moving_high,moving_low,serial,1,release,moving_registry,
                               exported_images[slot].resource,0,kind};
    return result;
}
static int moving_receive(MPCReleaseMessage expected, MPCReleaseMessage *actual) {
    if (!mpc_channel_receive(&moving_channel, &expected, actual, 10000) || !actual->registry ||
        (moving_registry && actual->registry != moving_registry) || actual->release != expected.release ||
        actual->code != (expected.kind == MPC_RELEASE_COMPLETED ? 4u : 0u)) return 0;
    moving_registry = actual->registry; return 1;
}

static int image_reject(const char *stage, int code) {
    printf(MPC_SCANOUT_PREFIX "_REJECTED {\"schema\":1,\"run\":\"%s\",\"stage\":\"%s\",\"code\":%d,"
           "\"host_memory_import_verified\":false,\"presentation_verified\":false}\n",
           image_run ? image_run : "missing", stage, code);
    fflush(stdout);
    return 21;
}
static int image_extensions(VkPhysicalDevice physical, VkExtensionProperties *extensions,
                            uint32_t count, const char **enabled, uint32_t *enabled_count) {
    image_run = getenv(MPC_SCANOUT_NONCE_ENV);
    if (!image_run || strlen(image_run) != 32 || strspn(image_run, "0123456789abcdef") != 32)
        return image_reject("fresh-nonce", 0);
    if (!mpc_wire_session(image_run, &moving_high, &moving_low) || !mpc_channel_open(&moving_channel))
        return image_reject("release-channel-open", errno);
    const char *wanted[] = { VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME,
                             VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME,
                             VK_EXT_IMAGE_DRM_FORMAT_MODIFIER_EXTENSION_NAME };
    for (unsigned w = 0; w < 3; ++w) {
        int found = 0;
        for (uint32_t i = 0; i < count; ++i) found |= !strcmp(extensions[i].extensionName, wanted[w]);
        if (!found) return image_reject(w == 2 ? "drm-modifier-extension" :
                                       w == 1 ? "dma-buf-extension" : "memory-fd-extension", 0);
        enabled[(*enabled_count)++] = wanted[w];
    }
    VkExternalImageFormatProperties output;
    VkImageFormatProperties2 properties;
    VkResult result = mpc_query_export_image(physical, vkGetPhysicalDeviceImageFormatProperties2, &properties, &output);
    printf(MPC_SCANOUT_PREFIX "_CAPABILITIES {\"schema\":1,\"run\":\"%s\",\"result\":%d,"
           "\"tiling\":\"drm-format-modifier\",\"drm_modifier\":0,"
           "\"external_features\":%u,\"compatible_handles\":%u,\"max_width\":%u,\"max_height\":%u}\n",
           image_run, result, output.externalMemoryProperties.externalMemoryFeatures,
           output.externalMemoryProperties.compatibleHandleTypes,
           properties.imageFormatProperties.maxExtent.width, properties.imageFormatProperties.maxExtent.height);
    if (!mpc_export_image_supported(result, &properties, &output, WIDTH, HEIGHT))
        return image_reject("drm-linear-bgra8-export-properties", result);
    return 0;
}
static int image_open_drm(void) {
    scanout_fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (scanout_fd < 0) return image_reject("drm-card-open", errno);
    if (drmSetMaster(scanout_fd)) return image_reject("drm-master", errno);
    drmModeRes *resources = drmModeGetResources(scanout_fd);
    if (!resources || resources->count_connectors < 1 || resources->count_connectors > 16 ||
        resources->count_crtcs < 1 || resources->count_crtcs > 32) return image_reject("drm-resources", errno);
    for (int c = 0; c < resources->count_connectors && !scanout_connector; ++c) {
        drmModeConnector *connector = drmModeGetConnector(scanout_fd, resources->connectors[c]);
        if (!connector) continue;
        if (connector->connection == DRM_MODE_CONNECTED && connector->count_modes > 0 && connector->count_modes <= 128) {
            for (int m = 0; m < connector->count_modes; ++m) {
                if (connector->modes[m].hdisplay != WIDTH || connector->modes[m].vdisplay != HEIGHT) continue;
                for (int e = 0; e < connector->count_encoders && !scanout_crtc; ++e) {
                    drmModeEncoder *encoder = drmModeGetEncoder(scanout_fd, connector->encoders[e]);
                    if (!encoder) continue;
                    for (int r = 0; r < resources->count_crtcs; ++r) {
                        if (encoder->possible_crtcs & (1u << r)) { scanout_crtc = resources->crtcs[r]; break; }
                    }
                    drmModeFreeEncoder(encoder);
                }
                if (scanout_crtc) { scanout_mode = connector->modes[m]; scanout_connector = connector->connector_id; break; }
            }
        }
        drmModeFreeConnector(connector);
    }
    drmModeFreeResources(resources);
    if (!scanout_connector || !scanout_crtc) return image_reject("drm-1280x720-mode", 0);
    return 0;
}
static int image_allocate(VkDevice device, const VkPhysicalDeviceMemoryProperties *memory) {
    for (unsigned i = 0; i < MPC_SCANOUT_FRAME_COUNT; ++i) {
        MPCImageExport *target = &exported_images[i];
        target->exported_fd = -1;
        const uint64_t linear = DRM_FORMAT_MOD_LINEAR;
        VkImageDrmFormatModifierListCreateInfoEXT modifier_list = {
            .sType = VK_STRUCTURE_TYPE_IMAGE_DRM_FORMAT_MODIFIER_LIST_CREATE_INFO_EXT,
            .drmFormatModifierCount = 1, .pDrmFormatModifiers = &linear };
        VkExternalMemoryImageCreateInfo external = { .sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_IMAGE_CREATE_INFO,
            .pNext = &modifier_list, .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
        VkImageCreateInfo info = { .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .pNext = &external,
            .imageType = VK_IMAGE_TYPE_2D, .format = VK_FORMAT_B8G8R8A8_UNORM, .extent = { WIDTH, HEIGHT, 1 },
            .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
            .tiling = VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT,
            .usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
        VkResult result = vkCreateImage(device, &info, NULL, &target->image);
        if (result) return image_reject("export-image-create", result);
        PFN_vkGetImageDrmFormatModifierPropertiesEXT get_modifier =
            (PFN_vkGetImageDrmFormatModifierPropertiesEXT)vkGetDeviceProcAddr(device, "vkGetImageDrmFormatModifierPropertiesEXT");
        if (!get_modifier) return image_reject("image-modifier-function", 0);
        VkImageDrmFormatModifierPropertiesEXT actual = { .sType = VK_STRUCTURE_TYPE_IMAGE_DRM_FORMAT_MODIFIER_PROPERTIES_EXT };
        result = get_modifier(device, target->image, &actual);
        if (result || actual.drmFormatModifier != DRM_FORMAT_MOD_LINEAR)
            return image_reject("image-modifier-not-linear", result ? result : 1);
        VkMemoryRequirements requirements;
        vkGetImageMemoryRequirements(device, target->image, &requirements);
        VkMemoryDedicatedAllocateInfo dedicated = { .sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO,
            .image = target->image };
        VkExportMemoryAllocateInfo export = { .sType = VK_STRUCTURE_TYPE_EXPORT_MEMORY_ALLOCATE_INFO,
            .pNext = &dedicated, .handleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
        VkMemoryAllocateInfo allocation = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &export,
            .allocationSize = requirements.size,
            .memoryTypeIndex = memory_type(memory, requirements.memoryTypeBits, 0, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT) };
        result = vkAllocateMemory(device, &allocation, NULL, &target->memory);
        if (result) return image_reject("export-memory-allocation", result);
        target->allocation = requirements.size;
        result = vkBindImageMemory(device, target->image, target->memory, 0);
        if (result) return image_reject("export-image-bind", result);
        VkImageSubresource subresource = { VK_IMAGE_ASPECT_MEMORY_PLANE_0_BIT_EXT, 0, 0 };
        vkGetImageSubresourceLayout(device, target->image, &subresource, &target->layout);
        VkSubresourceLayout *layout = &target->layout;
        /* Refuse unknown/non-linear or host-unalignable layout before native import. */
        if (layout->rowPitch < WIDTH * 4 || layout->rowPitch > UINT32_MAX || layout->rowPitch % 512 ||
            layout->offset > UINT32_MAX || layout->offset % 512 ||
            layout->offset > target->allocation || layout->rowPitch * HEIGHT > target->allocation - layout->offset)
            return image_reject("export-linear-layout-bounds", 0);
    }
    if (image_open_drm()) return 21;
    for (unsigned i=0; i<MPC_MOVING_BUFFERS; ++i) if (moving_register(device,i)) return 21;
    return 0;
}

static int moving_register(VkDevice device, unsigned slot) {
    MPCImageExport *target = &exported_images[slot];
    PFN_vkGetMemoryFdKHR get_fd = (PFN_vkGetMemoryFdKHR)vkGetDeviceProcAddr(device,"vkGetMemoryFdKHR");
    if (!get_fd) return image_reject("memory-fd-function",0);
    VkMemoryGetFdInfoKHR info = {.sType=VK_STRUCTURE_TYPE_MEMORY_GET_FD_INFO_KHR,
        .memory=target->memory,.handleType=VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT};
    VkResult result=get_fd(device,&info,&target->exported_fd);
    if (result || target->exported_fd<0) return image_reject("memory-fd-export",result);
    if (drmPrimeFDToHandle(scanout_fd,target->exported_fd,&target->gem_handle)) return image_reject("drm-prime-import",errno);
    struct drm_virtgpu_resource_info resource={.bo_handle=target->gem_handle};
    if (drmIoctl(scanout_fd,DRM_IOCTL_VIRTGPU_RESOURCE_INFO,&resource) || !resource.res_handle ||
        resource.size<target->layout.offset+target->layout.rowPitch*HEIGHT) return image_reject("drm-resource-identity",errno);
    target->resource=resource.res_handle;
    if (mpc_add_image_framebuffer(scanout_fd,WIDTH,HEIGHT,target->gem_handle,
                                 target->layout.rowPitch,target->layout.offset,&target->framebuffer))
        return image_reject("drm-addfb2",errno);
    printf("MPC_MOVE_CTL {\"schema\":1,\"type\":\"register\",\"run\":\"%s\",\"slot\":%u,"
           "\"resource_id\":%u,\"incarnation\":1,\"width\":%u,\"height\":%u,\"format\":80,"
           "\"row_pitch\":%" PRIu64 ",\"offset\":%" PRIu64 ",\"backing_bytes\":%" PRIu64 "}\n",
           image_run,slot,target->resource,WIDTH,HEIGHT,(uint64_t)target->layout.rowPitch,
           (uint64_t)target->layout.offset,(uint64_t)target->allocation);
    fflush(stdout);
    MPCReleaseMessage actual;
    if (!moving_receive(moving_expected(slot,MPC_RELEASE_REGISTERED,0,0),&actual)) return image_reject("register-response",0);
    return 0;
}

static int image_reacquire(VkDevice device,VkQueue queue,VkCommandBuffer command,VkFence fence,
                           unsigned pass,uint32_t family) {
    unsigned slot=pass%MPC_MOVING_BUFFERS;
    if (!moving_serial[slot]) return 0;
    if (!moving_release[slot] || moving_owned[slot]) return image_reject("premature-acquire",0);
    VkResult result=vkResetCommandBuffer(command,0);
    VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        .flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    if (!result) result=vkBeginCommandBuffer(command,&begin);
    if (result) return image_reject("acquire-command-begin",result);
    VkImageMemoryBarrier acquire={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask=0,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,
        .oldLayout=VK_IMAGE_LAYOUT_GENERAL,.newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        .srcQueueFamilyIndex=VK_QUEUE_FAMILY_EXTERNAL,.dstQueueFamilyIndex=family,
        .image=exported_images[slot].image,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,
                          0,0,NULL,0,NULL,1,&acquire);
    result=vkEndCommandBuffer(command);
    if (!result) result=vkResetFences(device,1,&fence);
    VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&command};
    if (!result) result=vkQueueSubmit(queue,1,&submit,fence);
    if (!result) result=vkWaitForFences(device,1,&fence,VK_TRUE,UINT64_C(30000000000));
    if (result) return image_reject("acquire-fence",result);
    ++moving_submission;
    printf("MPC_MOVE_CTL {\"schema\":1,\"type\":\"reacquired\",\"run\":\"%s\",\"resource_id\":%u,"
           "\"serial\":%" PRIu64 ",\"incarnation\":1,\"release\":%" PRIu64 ","
           "\"acquire_fence\":%" PRIu64 ",\"acquire_fence_completed\":true}\n",
           image_run,exported_images[slot].resource,moving_serial[slot],moving_release[slot],moving_submission);
    fflush(stdout);
    MPCReleaseMessage actual;
    if (!moving_receive(moving_expected(slot,MPC_RELEASE_REACQUIRED,moving_serial[slot],moving_release[slot]),&actual))
        return image_reject("acquire-response",0);
    moving_owned[slot]=1;
    return 0;
}

static void image_copy(VkCommandBuffer command,VkImage source,unsigned pass,uint32_t family) {
    unsigned slot=pass%MPC_MOVING_BUFFERS;
    VkImage image=exported_images[slot].image;
    if (!moving_owned[slot]) {
        VkImageMemoryBarrier initial={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=image,
            .subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
        vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,
                             0,0,NULL,0,NULL,1,&initial);
    }
    VkImageCopy copy={.srcSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},
        .dstSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.extent={WIDTH,HEIGHT,1}};
    vkCmdCopyImage(command,source,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
    VkImageMemoryBarrier release={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
        .newLayout=VK_IMAGE_LAYOUT_GENERAL,.srcQueueFamilyIndex=family,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_EXTERNAL,
        .image=image,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
    vkCmdPipelineBarrier(command,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,
                         0,0,NULL,0,NULL,1,&release);
    moving_owned[slot]=0;
}

static int image_install(VkDevice device,unsigned pass,uint32_t phase) {
    (void)device;
    unsigned slot=pass%MPC_MOVING_BUFFERS;
    MPCImageExport *target=&exported_images[slot];
    uint64_t serial=pass+1;
    ++moving_submission;
    printf("MPC_MOVE_CTL {\"schema\":1,\"type\":\"offer\",\"run\":\"%s\",\"resource_id\":%u,"
           "\"incarnation\":1,\"serial\":%" PRIu64 ",\"phase\":%u,\"producer_fence\":%" PRIu64 ","
           "\"producer_fence_completed\":true,\"external_queue_release\":true}\n",
           image_run,target->resource,serial,phase,moving_submission);
    fflush(stdout);
    MPCReleaseMessage actual;
    if (!moving_receive(moving_expected(slot,MPC_RELEASE_ARMED,serial,0),&actual)) return image_reject("arm-response",0);
    if (drmModeSetCrtc(scanout_fd,scanout_crtc,target->framebuffer,0,0,&scanout_connector,1,&scanout_mode))
        return image_reject("drm-setcrtc",errno);
    drmModeClip clip={0,0,WIDTH,HEIGHT};
    if (drmModeDirtyFB(scanout_fd,target->framebuffer,&clip,1)) return image_reject("drm-dirtyfb",errno);
    MPCReleaseMessage expected=moving_expected(slot,MPC_RELEASE_COMPLETED,serial,0);
    if (!mpc_channel_receive(&moving_channel,&expected,&actual,10000) || actual.code!=4 || !actual.release ||
        actual.registry!=moving_registry) return image_reject("native-reader-release",0);
    moving_serial[slot]=serial;moving_release[slot]=actual.release;
    printf("MPC_MOVE_RELEASE_RECEIVED {\"schema\":1,\"run\":\"%s\",\"resource_id\":%u,\"serial\":%" PRIu64 ","
           "\"incarnation\":1,\"release\":%" PRIu64 ",\"native_registry_id\":%" PRIu64 ",\"code\":4}\n",
           image_run,target->resource,serial,actual.release,actual.registry);
    fflush(stdout);
    return 0;
}

static int image_cleanup(VkDevice device,VkQueue queue,VkCommandBuffer command,VkFence fence,uint32_t family) {
    for (unsigned i=0;i<MPC_MOVING_BUFFERS;++i)
        if (image_reacquire(device,queue,command,fence,MPC_MOVING_FRAMES+i,family)) return 21;
    printf("MPC_MOVE_CTL {\"schema\":1,\"type\":\"finish\",\"run\":\"%s\",\"frames\":%u,\"buffers\":3}\n",image_run,MPC_MOVING_FRAMES);
    fflush(stdout);
    MPCReleaseMessage expected={moving_high,moving_low,0,0,0,moving_registry,0,0,MPC_RELEASE_FINISHED},actual;
    if (!moving_receive(expected,&actual)) return image_reject("finish-response",0);
    if (drmModeSetCrtc(scanout_fd,scanout_crtc,0,0,0,NULL,0,NULL)) return image_reject("drm-disable",errno);
    for (unsigned i=0;i<MPC_MOVING_BUFFERS;++i) {
        MPCImageExport *target=&exported_images[i];
        if (drmModeRmFB(scanout_fd,target->framebuffer)) return image_reject("drm-rmfb",errno);
        struct drm_gem_close close_gem={.handle=target->gem_handle};
        if (drmIoctl(scanout_fd,DRM_IOCTL_GEM_CLOSE,&close_gem)) return image_reject("drm-gem-close",errno);
        close(target->exported_fd);vkDestroyImage(device,target->image,NULL);vkFreeMemory(device,target->memory,NULL);
    }
    close(scanout_fd);mpc_channel_close(&moving_channel);
    printf("MPC_MOVE_EXIT {\"schema\":1,\"run\":\"%s\",\"frames\":%u,\"buffers\":3,\"status\":0,"
           "\"scanout_disabled\":true,\"images_released\":true,\"presentation_verified\":false}\n",image_run,MPC_MOVING_FRAMES);
    return 0;
}
#endif

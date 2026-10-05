/* SPDX-License-Identifier: MIT
 * Read-only prerequisite inventory, never compositor/render/FPS acceptance. */
#include <vulkan/vulkan.h>
#include <xf86drm.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/utsname.h>
#include <unistd.h>
#include "renderer_classification.h"

static int reject(const char *stage,int code) {
    printf("MPC_COMPOSITOR_REJECTED stage=%s code=%d\n",stage,code);
    return code;
}
static void string(const char *s) {
    putchar('"');
    for(const unsigned char *p=(const unsigned char *)s;*p;p++) {
        if(*p=='"'||*p=='\\')printf("\\%c",*p);
        else if(*p<32)printf("\\u%04x",*p);else putchar(*p);
    }
    putchar('"');
}
static int extension(const VkExtensionProperties *e,uint32_t n,const char *name) {
    for(uint32_t i=0;i<n;i++)if(!strcmp(e[i].extensionName,name))return 1;
    return 0;
}
int main(void) {
    const char *nonce=getenv("MPC_COMPOSITOR_RUN");
    if(!nonce||strlen(nonce)!=32||strspn(nonce,"0123456789abcdef")!=32)return reject("nonce",64);
    struct utsname machine;
    if(uname(&machine)||strcmp(machine.machine,"aarch64"))return reject("arm64-linux",65);
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="My-pc compositor capability inventory",.apiVersion=VK_API_VERSION_1_2};
    VkInstanceCreateInfo ci={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};
    VkInstance instance=VK_NULL_HANDLE;
    VkResult result=vkCreateInstance(&ci,NULL,&instance);
    if(result!=VK_SUCCESS)return reject("instance",3);
    int status=3;
    uint32_t count=0;
    VkPhysicalDevice devices[16];
    if(vkEnumeratePhysicalDevices(instance,&count,NULL)!=VK_SUCCESS||!count||count>16)goto done;
    if(vkEnumeratePhysicalDevices(instance,&count,devices)!=VK_SUCCESS||count!=1) {
        status=reject("ambiguous-device",4);goto done;
    }
    VkPhysicalDevice device=devices[0];
    VkPhysicalDeviceProperties base;
    vkGetPhysicalDeviceProperties(device,&base);
    if(base.deviceType==VK_PHYSICAL_DEVICE_TYPE_CPU||mpc_renderer_is_software(base.deviceName)) {
        status=reject("software-renderer",20);goto done;
    }
    if(base.apiVersion<VK_API_VERSION_1_2) {status=reject("vulkan-1.2",21);goto done;}
    uint32_t n=0;
    if(vkEnumerateDeviceExtensionProperties(device,NULL,&n,NULL)!=VK_SUCCESS||!n||n>4096)goto done;
    VkExtensionProperties *ext=calloc(n,sizeof(*ext));
    if(!ext)goto done;
    result=vkEnumerateDeviceExtensionProperties(device,NULL,&n,ext);
    if(result!=VK_SUCCESS) {free(ext);goto done;}
    int drm=extension(ext,n,VK_EXT_PHYSICAL_DEVICE_DRM_EXTENSION_NAME);
    int dma=extension(ext,n,VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME);
    int modifier=extension(ext,n,VK_EXT_IMAGE_DRM_FORMAT_MODIFIER_EXTENSION_NAME);
    int memoryfd=extension(ext,n,VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME);
    int semfd=extension(ext,n,VK_KHR_EXTERNAL_SEMAPHORE_FD_EXTENSION_NAME);
    int image_list=extension(ext,n,VK_KHR_IMAGE_FORMAT_LIST_EXTENSION_NAME);
    int foreign=extension(ext,n,VK_EXT_QUEUE_FAMILY_FOREIGN_EXTENSION_NAME);
    int timeline_ext=extension(ext,n,VK_KHR_TIMELINE_SEMAPHORE_EXTENSION_NAME);
    int sync2_ext=extension(ext,n,VK_KHR_SYNCHRONIZATION_2_EXTENSION_NAME);
    free(ext);
    VkPhysicalDeviceDrmPropertiesEXT identity={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRM_PROPERTIES_EXT};
    VkPhysicalDeviceProperties2 properties={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=drm?&identity:NULL};
    vkGetPhysicalDeviceProperties2(device,&properties);
    VkPhysicalDeviceTimelineSemaphoreFeatures timeline={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_TIMELINE_SEMAPHORE_FEATURES};
    VkPhysicalDeviceSynchronization2Features sync2={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SYNCHRONIZATION_2_FEATURES,.pNext=&timeline};
    VkPhysicalDeviceFeatures2 features={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
        .pNext=(sync2_ext||base.apiVersion>=VK_API_VERSION_1_3)?(void *)&sync2:(void *)&timeline};
    vkGetPhysicalDeviceFeatures2(device,&features);
    VkPhysicalDeviceExternalSemaphoreInfo seminfo={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_SEMAPHORE_INFO,.handleType=VK_EXTERNAL_SEMAPHORE_HANDLE_TYPE_SYNC_FD_BIT};
    VkExternalSemaphoreProperties sem={.sType=VK_STRUCTURE_TYPE_EXTERNAL_SEMAPHORE_PROPERTIES};
    if(semfd)vkGetPhysicalDeviceExternalSemaphoreProperties(device,&seminfo,&sem);
    VkExternalImageFormatProperties external={.sType=VK_STRUCTURE_TYPE_EXTERNAL_IMAGE_FORMAT_PROPERTIES};
    VkImageFormatProperties2 image={.sType=VK_STRUCTURE_TYPE_IMAGE_FORMAT_PROPERTIES_2,.pNext=&external};
    VkPhysicalDeviceImageDrmFormatModifierInfoEXT layout={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_DRM_FORMAT_MODIFIER_INFO_EXT,.drmFormatModifier=0,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    VkPhysicalDeviceExternalImageFormatInfo handle={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_IMAGE_FORMAT_INFO,.pNext=&layout,.handleType=VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT};
    VkPhysicalDeviceImageFormatInfo2 format={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_FORMAT_INFO_2,.pNext=&handle,.format=VK_FORMAT_B8G8R8A8_UNORM,.type=VK_IMAGE_TYPE_2D,.tiling=VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT,.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_SAMPLED_BIT};
    VkResult image_result=VK_ERROR_EXTENSION_NOT_PRESENT;
    if(dma&&modifier&&memoryfd)image_result=vkGetPhysicalDeviceImageFormatProperties2(device,&format,&image);
    int fd=-1,matched=0,atomic=0;
    uint64_t syncobj=0,syncobj_timeline=0;
    if(drm&&identity.hasPrimary)for(unsigned i=0;i<16;i++) {
        char path[64];snprintf(path,sizeof(path),"/dev/dri/card%u",i);
        int candidate=open(path,O_RDWR|O_CLOEXEC);struct stat st;
        if(candidate<0)continue;
        if(!fstat(candidate,&st)&&S_ISCHR(st.st_mode)&&
           (int64_t)major(st.st_rdev)==identity.primaryMajor&&(int64_t)minor(st.st_rdev)==identity.primaryMinor) {
            fd=candidate;matched=1;break;
        }
        close(candidate);
    }
    if(fd>=0) {
        atomic=drmSetClientCap(fd,DRM_CLIENT_CAP_ATOMIC,1)==0;
        if(drmGetCap(fd,DRM_CAP_SYNCOBJ,&syncobj))syncobj=0;
        if(drmGetCap(fd,DRM_CAP_SYNCOBJ_TIMELINE,&syncobj_timeline))syncobj_timeline=0;
        close(fd);
    }
    printf("MPC_COMPOSITOR_CAPABILITIES {\"schema\":1,\"scope\":\"query-only-linux-vulkan-compositor-prerequisites\",\"run\":");string(nonce);
    printf(",\"renderer\":");string(base.deviceName);
    printf(",\"memory_fd_extension\":%s,\"dma_buf_extension\":%s,\"drm_modifier_extension\":%s,\"semaphore_fd_extension\":%s",
        memoryfd?"true":"false",dma?"true":"false",modifier?"true":"false",semfd?"true":"false");
    printf(",\"image_format_list_extension\":%s,\"queue_family_foreign_extension\":%s,\"timeline_semaphore_extension\":%s,\"synchronization2_extension\":%s,\"synchronization2_feature\":%s",
        image_list?"true":"false",foreign?"true":"false",timeline_ext?"true":"false",sync2_ext?"true":"false",sync2.synchronization2?"true":"false");
    printf(",\"software\":false,\"api_version\":%u,\"physical_device_drm\":%s,\"has_primary\":%s,\"has_render\":%s,\"primary_node_matched\":%s,\"atomic_client_cap\":%s,\"drm_syncobj\":%" PRIu64 ",\"drm_syncobj_timeline\":%" PRIu64 ",\"vulkan_timeline\":%s,\"sync_fd_semaphore_features\":%u,\"bgra_linear_dmabuf_query_result\":%d,\"bgra_linear_dmabuf_memory_features\":%u,\"max_width\":%u,\"max_height\":%u,\"compositor_verified\":false,\"allocation_import_verified\":false,\"client_release_verified\":false,\"desktop_verified\":false,\"fps_verified\":false}\n",
        base.apiVersion,drm?"true":"false",identity.hasPrimary?"true":"false",identity.hasRender?"true":"false",matched?"true":"false",atomic?"true":"false",syncobj,syncobj_timeline,timeline.timelineSemaphore?"true":"false",sem.externalSemaphoreFeatures,image_result,external.externalMemoryProperties.externalMemoryFeatures,image.imageFormatProperties.maxExtent.width,image.imageFormatProperties.maxExtent.height);
    // A successful inventory is not a compositor-compatibility verdict. Missing
    // properties are retained as measurements; an allocator/import test follows.
    status=0;
done:
    vkDestroyInstance(instance,NULL);
    return status;
}

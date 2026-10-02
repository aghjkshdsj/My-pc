/* Fresh native-host adapter of our own shared offscreen diagnostic.
 * No Linux execution, presentation, or gameplay is performed here. */
#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>
#include <dlfcn.h>
#include <fcntl.h>
#include <unistd.h>
#if __has_include(<vulkan/vulkan.h>)
#include <vulkan/vulkan.h>
static _Thread_local jmp_buf mpc_abort;
static _Thread_local FILE *mpc_receipt;
static _Noreturn void mpc_abort_draw(int code) {
    fflush(stdout); fflush(stderr);
    longjmp(mpc_abort, code ? code : 1);
}
static PFN_vkAllocateCommandBuffers mpc_vkAllocateCommandBuffers;
static PFN_vkAllocateMemory mpc_vkAllocateMemory;
static PFN_vkBeginCommandBuffer mpc_vkBeginCommandBuffer;
static PFN_vkBindBufferMemory mpc_vkBindBufferMemory;
static PFN_vkBindImageMemory mpc_vkBindImageMemory;
static PFN_vkCmdBeginRenderPass mpc_vkCmdBeginRenderPass;
static PFN_vkCmdBindPipeline mpc_vkCmdBindPipeline;
static PFN_vkCmdCopyImageToBuffer mpc_vkCmdCopyImageToBuffer;
static PFN_vkCmdDraw mpc_vkCmdDraw;
static PFN_vkCmdEndRenderPass mpc_vkCmdEndRenderPass;
static PFN_vkCmdPipelineBarrier mpc_vkCmdPipelineBarrier;
static PFN_vkCmdPushConstants mpc_vkCmdPushConstants;
static PFN_vkCreateBuffer mpc_vkCreateBuffer;
static PFN_vkCreateCommandPool mpc_vkCreateCommandPool;
static PFN_vkCreateDevice mpc_vkCreateDevice;
static PFN_vkCreateFence mpc_vkCreateFence;
static PFN_vkCreateFramebuffer mpc_vkCreateFramebuffer;
static PFN_vkCreateGraphicsPipelines mpc_vkCreateGraphicsPipelines;
static PFN_vkCreateImage mpc_vkCreateImage;
static PFN_vkCreateImageView mpc_vkCreateImageView;
static PFN_vkCreateInstance mpc_vkCreateInstance;
static PFN_vkCreatePipelineLayout mpc_vkCreatePipelineLayout;
static PFN_vkCreateRenderPass mpc_vkCreateRenderPass;
static PFN_vkCreateShaderModule mpc_vkCreateShaderModule;
static PFN_vkDestroyBuffer mpc_vkDestroyBuffer;
static PFN_vkDestroyCommandPool mpc_vkDestroyCommandPool;
static PFN_vkDestroyDevice mpc_vkDestroyDevice;
static PFN_vkDestroyFence mpc_vkDestroyFence;
static PFN_vkDestroyFramebuffer mpc_vkDestroyFramebuffer;
static PFN_vkDestroyImage mpc_vkDestroyImage;
static PFN_vkDestroyImageView mpc_vkDestroyImageView;
static PFN_vkDestroyInstance mpc_vkDestroyInstance;
static PFN_vkDestroyPipeline mpc_vkDestroyPipeline;
static PFN_vkDestroyPipelineLayout mpc_vkDestroyPipelineLayout;
static PFN_vkDestroyRenderPass mpc_vkDestroyRenderPass;
static PFN_vkDestroyShaderModule mpc_vkDestroyShaderModule;
static PFN_vkDeviceWaitIdle mpc_vkDeviceWaitIdle;
static PFN_vkEndCommandBuffer mpc_vkEndCommandBuffer;
static PFN_vkEnumerateDeviceExtensionProperties mpc_vkEnumerateDeviceExtensionProperties;
static PFN_vkEnumerateInstanceExtensionProperties mpc_vkEnumerateInstanceExtensionProperties;
static PFN_vkEnumerateInstanceLayerProperties mpc_vkEnumerateInstanceLayerProperties;
static PFN_vkEnumeratePhysicalDevices mpc_vkEnumeratePhysicalDevices;
static PFN_vkFreeMemory mpc_vkFreeMemory;
static PFN_vkGetBufferMemoryRequirements mpc_vkGetBufferMemoryRequirements;
static PFN_vkGetDeviceQueue mpc_vkGetDeviceQueue;
static PFN_vkGetImageMemoryRequirements mpc_vkGetImageMemoryRequirements;
static PFN_vkGetInstanceProcAddr mpc_vkGetInstanceProcAddr;
static PFN_vkGetPhysicalDeviceFeatures mpc_vkGetPhysicalDeviceFeatures;
static PFN_vkGetPhysicalDeviceFormatProperties mpc_vkGetPhysicalDeviceFormatProperties;
static PFN_vkGetPhysicalDeviceMemoryProperties mpc_vkGetPhysicalDeviceMemoryProperties;
static PFN_vkGetPhysicalDeviceProperties mpc_vkGetPhysicalDeviceProperties;
static PFN_vkGetPhysicalDeviceQueueFamilyProperties mpc_vkGetPhysicalDeviceQueueFamilyProperties;
static PFN_vkInvalidateMappedMemoryRanges mpc_vkInvalidateMappedMemoryRanges;
static PFN_vkMapMemory mpc_vkMapMemory;
static PFN_vkQueueSubmit mpc_vkQueueSubmit;
static PFN_vkResetCommandBuffer mpc_vkResetCommandBuffer;
static PFN_vkResetFences mpc_vkResetFences;
static PFN_vkUnmapMemory mpc_vkUnmapMemory;
static PFN_vkWaitForFences mpc_vkWaitForFences;
#define vkAllocateCommandBuffers mpc_vkAllocateCommandBuffers
#define vkAllocateMemory mpc_vkAllocateMemory
#define vkBeginCommandBuffer mpc_vkBeginCommandBuffer
#define vkBindBufferMemory mpc_vkBindBufferMemory
#define vkBindImageMemory mpc_vkBindImageMemory
#define vkCmdBeginRenderPass mpc_vkCmdBeginRenderPass
#define vkCmdBindPipeline mpc_vkCmdBindPipeline
#define vkCmdCopyImageToBuffer mpc_vkCmdCopyImageToBuffer
#define vkCmdDraw mpc_vkCmdDraw
#define vkCmdEndRenderPass mpc_vkCmdEndRenderPass
#define vkCmdPipelineBarrier mpc_vkCmdPipelineBarrier
#define vkCmdPushConstants mpc_vkCmdPushConstants
#define vkCreateBuffer mpc_vkCreateBuffer
#define vkCreateCommandPool mpc_vkCreateCommandPool
#define vkCreateDevice mpc_vkCreateDevice
#define vkCreateFence mpc_vkCreateFence
#define vkCreateFramebuffer mpc_vkCreateFramebuffer
#define vkCreateGraphicsPipelines mpc_vkCreateGraphicsPipelines
#define vkCreateImage mpc_vkCreateImage
#define vkCreateImageView mpc_vkCreateImageView
#define vkCreateInstance mpc_vkCreateInstance
#define vkCreatePipelineLayout mpc_vkCreatePipelineLayout
#define vkCreateRenderPass mpc_vkCreateRenderPass
#define vkCreateShaderModule mpc_vkCreateShaderModule
#define vkDestroyBuffer mpc_vkDestroyBuffer
#define vkDestroyCommandPool mpc_vkDestroyCommandPool
#define vkDestroyDevice mpc_vkDestroyDevice
#define vkDestroyFence mpc_vkDestroyFence
#define vkDestroyFramebuffer mpc_vkDestroyFramebuffer
#define vkDestroyImage mpc_vkDestroyImage
#define vkDestroyImageView mpc_vkDestroyImageView
#define vkDestroyInstance mpc_vkDestroyInstance
#define vkDestroyPipeline mpc_vkDestroyPipeline
#define vkDestroyPipelineLayout mpc_vkDestroyPipelineLayout
#define vkDestroyRenderPass mpc_vkDestroyRenderPass
#define vkDestroyShaderModule mpc_vkDestroyShaderModule
#define vkDeviceWaitIdle mpc_vkDeviceWaitIdle
#define vkEndCommandBuffer mpc_vkEndCommandBuffer
#define vkEnumerateDeviceExtensionProperties mpc_vkEnumerateDeviceExtensionProperties
#define vkEnumerateInstanceExtensionProperties mpc_vkEnumerateInstanceExtensionProperties
#define vkEnumerateInstanceLayerProperties mpc_vkEnumerateInstanceLayerProperties
#define vkEnumeratePhysicalDevices mpc_vkEnumeratePhysicalDevices
#define vkFreeMemory mpc_vkFreeMemory
#define vkGetBufferMemoryRequirements mpc_vkGetBufferMemoryRequirements
#define vkGetDeviceQueue mpc_vkGetDeviceQueue
#define vkGetImageMemoryRequirements mpc_vkGetImageMemoryRequirements
#define vkGetInstanceProcAddr mpc_vkGetInstanceProcAddr
#define vkGetPhysicalDeviceFeatures mpc_vkGetPhysicalDeviceFeatures
#define vkGetPhysicalDeviceFormatProperties mpc_vkGetPhysicalDeviceFormatProperties
#define vkGetPhysicalDeviceMemoryProperties mpc_vkGetPhysicalDeviceMemoryProperties
#define vkGetPhysicalDeviceProperties mpc_vkGetPhysicalDeviceProperties
#define vkGetPhysicalDeviceQueueFamilyProperties mpc_vkGetPhysicalDeviceQueueFamilyProperties
#define vkInvalidateMappedMemoryRanges mpc_vkInvalidateMappedMemoryRanges
#define vkMapMemory mpc_vkMapMemory
#define vkQueueSubmit mpc_vkQueueSubmit
#define vkResetCommandBuffer mpc_vkResetCommandBuffer
#define vkResetFences mpc_vkResetFences
#define vkUnmapMemory mpc_vkUnmapMemory
#define vkWaitForFences mpc_vkWaitForFences
#define exit(code) mpc_abort_draw(code)
#define main mpc_shared_vulkan_main
#define MPC_VK_DIAGNOSTIC_STREAM mpc_receipt
#define MPC_VK_DIAGNOSTIC_PREFIX ""
#include "../Guest/vk_gate.c"
#undef main
#undef exit
int MPCNativeVulkanDraw(void *library, const char *vertex, const char *fragment, const char *receipt_path) {
    mpc_vkAllocateCommandBuffers = (PFN_vkAllocateCommandBuffers)dlsym(library, "vkAllocateCommandBuffers");
    if (!mpc_vkAllocateCommandBuffers) { fprintf(stderr, "Missing Vulkan export: vkAllocateCommandBuffers\\n"); return 90; }
    mpc_vkAllocateMemory = (PFN_vkAllocateMemory)dlsym(library, "vkAllocateMemory");
    if (!mpc_vkAllocateMemory) { fprintf(stderr, "Missing Vulkan export: vkAllocateMemory\\n"); return 90; }
    mpc_vkBeginCommandBuffer = (PFN_vkBeginCommandBuffer)dlsym(library, "vkBeginCommandBuffer");
    if (!mpc_vkBeginCommandBuffer) { fprintf(stderr, "Missing Vulkan export: vkBeginCommandBuffer\\n"); return 90; }
    mpc_vkBindBufferMemory = (PFN_vkBindBufferMemory)dlsym(library, "vkBindBufferMemory");
    if (!mpc_vkBindBufferMemory) { fprintf(stderr, "Missing Vulkan export: vkBindBufferMemory\\n"); return 90; }
    mpc_vkBindImageMemory = (PFN_vkBindImageMemory)dlsym(library, "vkBindImageMemory");
    if (!mpc_vkBindImageMemory) { fprintf(stderr, "Missing Vulkan export: vkBindImageMemory\\n"); return 90; }
    mpc_vkCmdBeginRenderPass = (PFN_vkCmdBeginRenderPass)dlsym(library, "vkCmdBeginRenderPass");
    if (!mpc_vkCmdBeginRenderPass) { fprintf(stderr, "Missing Vulkan export: vkCmdBeginRenderPass\\n"); return 90; }
    mpc_vkCmdBindPipeline = (PFN_vkCmdBindPipeline)dlsym(library, "vkCmdBindPipeline");
    if (!mpc_vkCmdBindPipeline) { fprintf(stderr, "Missing Vulkan export: vkCmdBindPipeline\\n"); return 90; }
    mpc_vkCmdCopyImageToBuffer = (PFN_vkCmdCopyImageToBuffer)dlsym(library, "vkCmdCopyImageToBuffer");
    if (!mpc_vkCmdCopyImageToBuffer) { fprintf(stderr, "Missing Vulkan export: vkCmdCopyImageToBuffer\\n"); return 90; }
    mpc_vkCmdDraw = (PFN_vkCmdDraw)dlsym(library, "vkCmdDraw");
    if (!mpc_vkCmdDraw) { fprintf(stderr, "Missing Vulkan export: vkCmdDraw\\n"); return 90; }
    mpc_vkCmdEndRenderPass = (PFN_vkCmdEndRenderPass)dlsym(library, "vkCmdEndRenderPass");
    if (!mpc_vkCmdEndRenderPass) { fprintf(stderr, "Missing Vulkan export: vkCmdEndRenderPass\\n"); return 90; }
    mpc_vkCmdPipelineBarrier = (PFN_vkCmdPipelineBarrier)dlsym(library, "vkCmdPipelineBarrier");
    if (!mpc_vkCmdPipelineBarrier) { fprintf(stderr, "Missing Vulkan export: vkCmdPipelineBarrier\\n"); return 90; }
    mpc_vkCmdPushConstants = (PFN_vkCmdPushConstants)dlsym(library, "vkCmdPushConstants");
    if (!mpc_vkCmdPushConstants) { fprintf(stderr, "Missing Vulkan export: vkCmdPushConstants\\n"); return 90; }
    mpc_vkCreateBuffer = (PFN_vkCreateBuffer)dlsym(library, "vkCreateBuffer");
    if (!mpc_vkCreateBuffer) { fprintf(stderr, "Missing Vulkan export: vkCreateBuffer\\n"); return 90; }
    mpc_vkCreateCommandPool = (PFN_vkCreateCommandPool)dlsym(library, "vkCreateCommandPool");
    if (!mpc_vkCreateCommandPool) { fprintf(stderr, "Missing Vulkan export: vkCreateCommandPool\\n"); return 90; }
    mpc_vkCreateDevice = (PFN_vkCreateDevice)dlsym(library, "vkCreateDevice");
    if (!mpc_vkCreateDevice) { fprintf(stderr, "Missing Vulkan export: vkCreateDevice\\n"); return 90; }
    mpc_vkCreateFence = (PFN_vkCreateFence)dlsym(library, "vkCreateFence");
    if (!mpc_vkCreateFence) { fprintf(stderr, "Missing Vulkan export: vkCreateFence\\n"); return 90; }
    mpc_vkCreateFramebuffer = (PFN_vkCreateFramebuffer)dlsym(library, "vkCreateFramebuffer");
    if (!mpc_vkCreateFramebuffer) { fprintf(stderr, "Missing Vulkan export: vkCreateFramebuffer\\n"); return 90; }
    mpc_vkCreateGraphicsPipelines = (PFN_vkCreateGraphicsPipelines)dlsym(library, "vkCreateGraphicsPipelines");
    if (!mpc_vkCreateGraphicsPipelines) { fprintf(stderr, "Missing Vulkan export: vkCreateGraphicsPipelines\\n"); return 90; }
    mpc_vkCreateImage = (PFN_vkCreateImage)dlsym(library, "vkCreateImage");
    if (!mpc_vkCreateImage) { fprintf(stderr, "Missing Vulkan export: vkCreateImage\\n"); return 90; }
    mpc_vkCreateImageView = (PFN_vkCreateImageView)dlsym(library, "vkCreateImageView");
    if (!mpc_vkCreateImageView) { fprintf(stderr, "Missing Vulkan export: vkCreateImageView\\n"); return 90; }
    mpc_vkCreateInstance = (PFN_vkCreateInstance)dlsym(library, "vkCreateInstance");
    if (!mpc_vkCreateInstance) { fprintf(stderr, "Missing Vulkan export: vkCreateInstance\\n"); return 90; }
    mpc_vkCreatePipelineLayout = (PFN_vkCreatePipelineLayout)dlsym(library, "vkCreatePipelineLayout");
    if (!mpc_vkCreatePipelineLayout) { fprintf(stderr, "Missing Vulkan export: vkCreatePipelineLayout\\n"); return 90; }
    mpc_vkCreateRenderPass = (PFN_vkCreateRenderPass)dlsym(library, "vkCreateRenderPass");
    if (!mpc_vkCreateRenderPass) { fprintf(stderr, "Missing Vulkan export: vkCreateRenderPass\\n"); return 90; }
    mpc_vkCreateShaderModule = (PFN_vkCreateShaderModule)dlsym(library, "vkCreateShaderModule");
    if (!mpc_vkCreateShaderModule) { fprintf(stderr, "Missing Vulkan export: vkCreateShaderModule\\n"); return 90; }
    mpc_vkDestroyBuffer = (PFN_vkDestroyBuffer)dlsym(library, "vkDestroyBuffer");
    if (!mpc_vkDestroyBuffer) { fprintf(stderr, "Missing Vulkan export: vkDestroyBuffer\\n"); return 90; }
    mpc_vkDestroyCommandPool = (PFN_vkDestroyCommandPool)dlsym(library, "vkDestroyCommandPool");
    if (!mpc_vkDestroyCommandPool) { fprintf(stderr, "Missing Vulkan export: vkDestroyCommandPool\\n"); return 90; }
    mpc_vkDestroyDevice = (PFN_vkDestroyDevice)dlsym(library, "vkDestroyDevice");
    if (!mpc_vkDestroyDevice) { fprintf(stderr, "Missing Vulkan export: vkDestroyDevice\\n"); return 90; }
    mpc_vkDestroyFence = (PFN_vkDestroyFence)dlsym(library, "vkDestroyFence");
    if (!mpc_vkDestroyFence) { fprintf(stderr, "Missing Vulkan export: vkDestroyFence\\n"); return 90; }
    mpc_vkDestroyFramebuffer = (PFN_vkDestroyFramebuffer)dlsym(library, "vkDestroyFramebuffer");
    if (!mpc_vkDestroyFramebuffer) { fprintf(stderr, "Missing Vulkan export: vkDestroyFramebuffer\\n"); return 90; }
    mpc_vkDestroyImage = (PFN_vkDestroyImage)dlsym(library, "vkDestroyImage");
    if (!mpc_vkDestroyImage) { fprintf(stderr, "Missing Vulkan export: vkDestroyImage\\n"); return 90; }
    mpc_vkDestroyImageView = (PFN_vkDestroyImageView)dlsym(library, "vkDestroyImageView");
    if (!mpc_vkDestroyImageView) { fprintf(stderr, "Missing Vulkan export: vkDestroyImageView\\n"); return 90; }
    mpc_vkDestroyInstance = (PFN_vkDestroyInstance)dlsym(library, "vkDestroyInstance");
    if (!mpc_vkDestroyInstance) { fprintf(stderr, "Missing Vulkan export: vkDestroyInstance\\n"); return 90; }
    mpc_vkDestroyPipeline = (PFN_vkDestroyPipeline)dlsym(library, "vkDestroyPipeline");
    if (!mpc_vkDestroyPipeline) { fprintf(stderr, "Missing Vulkan export: vkDestroyPipeline\\n"); return 90; }
    mpc_vkDestroyPipelineLayout = (PFN_vkDestroyPipelineLayout)dlsym(library, "vkDestroyPipelineLayout");
    if (!mpc_vkDestroyPipelineLayout) { fprintf(stderr, "Missing Vulkan export: vkDestroyPipelineLayout\\n"); return 90; }
    mpc_vkDestroyRenderPass = (PFN_vkDestroyRenderPass)dlsym(library, "vkDestroyRenderPass");
    if (!mpc_vkDestroyRenderPass) { fprintf(stderr, "Missing Vulkan export: vkDestroyRenderPass\\n"); return 90; }
    mpc_vkDestroyShaderModule = (PFN_vkDestroyShaderModule)dlsym(library, "vkDestroyShaderModule");
    if (!mpc_vkDestroyShaderModule) { fprintf(stderr, "Missing Vulkan export: vkDestroyShaderModule\\n"); return 90; }
    mpc_vkDeviceWaitIdle = (PFN_vkDeviceWaitIdle)dlsym(library, "vkDeviceWaitIdle");
    if (!mpc_vkDeviceWaitIdle) { fprintf(stderr, "Missing Vulkan export: vkDeviceWaitIdle\\n"); return 90; }
    mpc_vkEndCommandBuffer = (PFN_vkEndCommandBuffer)dlsym(library, "vkEndCommandBuffer");
    if (!mpc_vkEndCommandBuffer) { fprintf(stderr, "Missing Vulkan export: vkEndCommandBuffer\\n"); return 90; }
    mpc_vkEnumerateDeviceExtensionProperties = (PFN_vkEnumerateDeviceExtensionProperties)dlsym(library, "vkEnumerateDeviceExtensionProperties");
    if (!mpc_vkEnumerateDeviceExtensionProperties) { fprintf(stderr, "Missing Vulkan export: vkEnumerateDeviceExtensionProperties\\n"); return 90; }
    mpc_vkEnumerateInstanceExtensionProperties = (PFN_vkEnumerateInstanceExtensionProperties)dlsym(library, "vkEnumerateInstanceExtensionProperties");
    if (!mpc_vkEnumerateInstanceExtensionProperties) { fprintf(stderr, "Missing Vulkan export: vkEnumerateInstanceExtensionProperties\\n"); return 90; }
    mpc_vkEnumerateInstanceLayerProperties = (PFN_vkEnumerateInstanceLayerProperties)dlsym(library, "vkEnumerateInstanceLayerProperties");
    if (!mpc_vkEnumerateInstanceLayerProperties) { fprintf(stderr, "Missing Vulkan export: vkEnumerateInstanceLayerProperties\\n"); return 90; }
    mpc_vkEnumeratePhysicalDevices = (PFN_vkEnumeratePhysicalDevices)dlsym(library, "vkEnumeratePhysicalDevices");
    if (!mpc_vkEnumeratePhysicalDevices) { fprintf(stderr, "Missing Vulkan export: vkEnumeratePhysicalDevices\\n"); return 90; }
    mpc_vkFreeMemory = (PFN_vkFreeMemory)dlsym(library, "vkFreeMemory");
    if (!mpc_vkFreeMemory) { fprintf(stderr, "Missing Vulkan export: vkFreeMemory\\n"); return 90; }
    mpc_vkGetBufferMemoryRequirements = (PFN_vkGetBufferMemoryRequirements)dlsym(library, "vkGetBufferMemoryRequirements");
    if (!mpc_vkGetBufferMemoryRequirements) { fprintf(stderr, "Missing Vulkan export: vkGetBufferMemoryRequirements\\n"); return 90; }
    mpc_vkGetDeviceQueue = (PFN_vkGetDeviceQueue)dlsym(library, "vkGetDeviceQueue");
    if (!mpc_vkGetDeviceQueue) { fprintf(stderr, "Missing Vulkan export: vkGetDeviceQueue\\n"); return 90; }
    mpc_vkGetImageMemoryRequirements = (PFN_vkGetImageMemoryRequirements)dlsym(library, "vkGetImageMemoryRequirements");
    if (!mpc_vkGetImageMemoryRequirements) { fprintf(stderr, "Missing Vulkan export: vkGetImageMemoryRequirements\\n"); return 90; }
    mpc_vkGetInstanceProcAddr = (PFN_vkGetInstanceProcAddr)dlsym(library, "vkGetInstanceProcAddr");
    if (!mpc_vkGetInstanceProcAddr) { fprintf(stderr, "Missing Vulkan export: vkGetInstanceProcAddr\\n"); return 90; }
    mpc_vkGetPhysicalDeviceFeatures = (PFN_vkGetPhysicalDeviceFeatures)dlsym(library, "vkGetPhysicalDeviceFeatures");
    if (!mpc_vkGetPhysicalDeviceFeatures) { fprintf(stderr, "Missing Vulkan export: vkGetPhysicalDeviceFeatures\\n"); return 90; }
    mpc_vkGetPhysicalDeviceFormatProperties = (PFN_vkGetPhysicalDeviceFormatProperties)dlsym(library, "vkGetPhysicalDeviceFormatProperties");
    if (!mpc_vkGetPhysicalDeviceFormatProperties) { fprintf(stderr, "Missing Vulkan export: vkGetPhysicalDeviceFormatProperties\\n"); return 90; }
    mpc_vkGetPhysicalDeviceMemoryProperties = (PFN_vkGetPhysicalDeviceMemoryProperties)dlsym(library, "vkGetPhysicalDeviceMemoryProperties");
    if (!mpc_vkGetPhysicalDeviceMemoryProperties) { fprintf(stderr, "Missing Vulkan export: vkGetPhysicalDeviceMemoryProperties\\n"); return 90; }
    mpc_vkGetPhysicalDeviceProperties = (PFN_vkGetPhysicalDeviceProperties)dlsym(library, "vkGetPhysicalDeviceProperties");
    if (!mpc_vkGetPhysicalDeviceProperties) { fprintf(stderr, "Missing Vulkan export: vkGetPhysicalDeviceProperties\\n"); return 90; }
    mpc_vkGetPhysicalDeviceQueueFamilyProperties = (PFN_vkGetPhysicalDeviceQueueFamilyProperties)dlsym(library, "vkGetPhysicalDeviceQueueFamilyProperties");
    if (!mpc_vkGetPhysicalDeviceQueueFamilyProperties) { fprintf(stderr, "Missing Vulkan export: vkGetPhysicalDeviceQueueFamilyProperties\\n"); return 90; }
    mpc_vkInvalidateMappedMemoryRanges = (PFN_vkInvalidateMappedMemoryRanges)dlsym(library, "vkInvalidateMappedMemoryRanges");
    if (!mpc_vkInvalidateMappedMemoryRanges) { fprintf(stderr, "Missing Vulkan export: vkInvalidateMappedMemoryRanges\\n"); return 90; }
    mpc_vkMapMemory = (PFN_vkMapMemory)dlsym(library, "vkMapMemory");
    if (!mpc_vkMapMemory) { fprintf(stderr, "Missing Vulkan export: vkMapMemory\\n"); return 90; }
    mpc_vkQueueSubmit = (PFN_vkQueueSubmit)dlsym(library, "vkQueueSubmit");
    if (!mpc_vkQueueSubmit) { fprintf(stderr, "Missing Vulkan export: vkQueueSubmit\\n"); return 90; }
    mpc_vkResetCommandBuffer = (PFN_vkResetCommandBuffer)dlsym(library, "vkResetCommandBuffer");
    if (!mpc_vkResetCommandBuffer) { fprintf(stderr, "Missing Vulkan export: vkResetCommandBuffer\\n"); return 90; }
    mpc_vkResetFences = (PFN_vkResetFences)dlsym(library, "vkResetFences");
    if (!mpc_vkResetFences) { fprintf(stderr, "Missing Vulkan export: vkResetFences\\n"); return 90; }
    mpc_vkUnmapMemory = (PFN_vkUnmapMemory)dlsym(library, "vkUnmapMemory");
    if (!mpc_vkUnmapMemory) { fprintf(stderr, "Missing Vulkan export: vkUnmapMemory\\n"); return 90; }
    mpc_vkWaitForFences = (PFN_vkWaitForFences)dlsym(library, "vkWaitForFences");
    if (!mpc_vkWaitForFences) { fprintf(stderr, "Missing Vulkan export: vkWaitForFences\\n"); return 90; }
    atomic_store(&validation_errors, 0);
    int receipt_fd = open(receipt_path, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (receipt_fd < 0) { perror("Vulkan receipt open"); return 92; }
    mpc_receipt = fdopen(receipt_fd, "w");
    if (!mpc_receipt) { close(receipt_fd); perror("Vulkan receipt stream"); return 92; }
    int interrupted = setjmp(mpc_abort);
    int result = interrupted;
    if (!interrupted) {
        char *arguments[] = {"native-vulkan-diagnostic", (char *)vertex, (char *)fragment};
        result = mpc_shared_vulkan_main(3, arguments);
    }
    int flush_failed = fflush(mpc_receipt);
    int stream_failed = ferror(mpc_receipt);
    int sync_failed = fsync(fileno(mpc_receipt));
    int close_failed = fclose(mpc_receipt);
    mpc_receipt = NULL;
    fflush(stdout); fflush(stderr);
    return flush_failed || stream_failed || sync_failed || close_failed ? 93 : result;
}
#else
int MPCNativeVulkanDraw(void *library, const char *vertex, const char *fragment, const char *receipt_path) {
    (void)library; (void)vertex; (void)fragment; (void)receipt_path;
    return 91; /* This host-only build did not receive pinned Vulkan headers. */
}
#endif

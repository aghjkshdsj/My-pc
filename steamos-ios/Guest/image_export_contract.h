/* Fresh Linux export-format query contract, MIT. No success override. */
#ifndef MPC_IMAGE_EXPORT_CONTRACT_H
#define MPC_IMAGE_EXPORT_CONTRACT_H
#include <vulkan/vulkan.h>
#include <drm_fourcc.h>

static inline VkResult mpc_query_export_image(VkPhysicalDevice physical,
        PFN_vkGetPhysicalDeviceImageFormatProperties2 query,
        VkImageFormatProperties2 *properties, VkExternalImageFormatProperties *output) {
    /* Venus rejects legacy tiling for DMA-BUF scanout. LINEAR is an explicit
     * DRM modifier here, not VK_IMAGE_TILING_LINEAR or an assumed layout. */
    VkPhysicalDeviceImageDrmFormatModifierInfoEXT modifier = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_DRM_FORMAT_MODIFIER_INFO_EXT,
        .drmFormatModifier = DRM_FORMAT_MOD_LINEAR, .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
    VkPhysicalDeviceExternalImageFormatInfo external = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_IMAGE_FORMAT_INFO,
        .pNext = &modifier, .handleType = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    VkPhysicalDeviceImageFormatInfo2 info = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_FORMAT_INFO_2, .pNext = &external,
        .format = VK_FORMAT_R8G8B8A8_UNORM, .type = VK_IMAGE_TYPE_2D,
        .tiling = VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT, .usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT };
    *output = (VkExternalImageFormatProperties){ .sType = VK_STRUCTURE_TYPE_EXTERNAL_IMAGE_FORMAT_PROPERTIES };
    *properties = (VkImageFormatProperties2){ .sType = VK_STRUCTURE_TYPE_IMAGE_FORMAT_PROPERTIES_2, .pNext = output };
    return query(physical, &info, properties);
}
static inline int mpc_export_image_supported(VkResult result,
        const VkImageFormatProperties2 *properties, const VkExternalImageFormatProperties *output,
        uint32_t width, uint32_t height) {
    return result == VK_SUCCESS &&
        (output->externalMemoryProperties.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_EXPORTABLE_BIT) &&
        (output->externalMemoryProperties.compatibleHandleTypes & VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT) &&
        properties->imageFormatProperties.maxExtent.width >= width &&
        properties->imageFormatProperties.maxExtent.height >= height &&
        (properties->imageFormatProperties.sampleCounts & VK_SAMPLE_COUNT_1_BIT);
}
#endif

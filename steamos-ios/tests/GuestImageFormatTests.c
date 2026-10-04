/* Query-only rejection fixtures. They are not GPU or device evidence. MIT. */
#include <assert.h>
#include <stdio.h>
#include "../Guest/image_export_contract.h"
static unsigned queries;
static VkResult query(VkPhysicalDevice physical, const VkPhysicalDeviceImageFormatInfo2 *info,
                      VkImageFormatProperties2 *properties) {
    (void)physical;
    ++queries;
    const VkPhysicalDeviceExternalImageFormatInfo *external = info->pNext;
    const VkPhysicalDeviceImageDrmFormatModifierInfoEXT *modifier = external->pNext;
    assert(info->sType == VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_FORMAT_INFO_2);
    assert(info->tiling == VK_IMAGE_TILING_DRM_FORMAT_MODIFIER_EXT);
    assert(info->format == VK_FORMAT_R8G8B8A8_UNORM && info->type == VK_IMAGE_TYPE_2D);
    assert(info->usage == VK_IMAGE_USAGE_TRANSFER_DST_BIT);
    assert(external->sType == VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_IMAGE_FORMAT_INFO);
    assert(external->handleType == VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT);
    assert(modifier && modifier->sType == VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_IMAGE_DRM_FORMAT_MODIFIER_INFO_EXT);
    assert(modifier->drmFormatModifier == DRM_FORMAT_MOD_LINEAR && !modifier->pNext);
    assert(modifier->sharingMode == VK_SHARING_MODE_EXCLUSIVE);
    VkExternalImageFormatProperties *output = properties->pNext;
    assert(output && output->sType == VK_STRUCTURE_TYPE_EXTERNAL_IMAGE_FORMAT_PROPERTIES);
    properties->imageFormatProperties = (VkImageFormatProperties){
        .maxExtent = {1280,720,1}, .sampleCounts = VK_SAMPLE_COUNT_1_BIT };
    output->externalMemoryProperties = (VkExternalMemoryProperties){
        .externalMemoryFeatures = VK_EXTERNAL_MEMORY_FEATURE_EXPORTABLE_BIT,
        .compatibleHandleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT };
    return VK_SUCCESS;
}
int main(void) {
    VkImageFormatProperties2 properties;
    VkExternalImageFormatProperties output;
    VkResult result = mpc_query_export_image(VK_NULL_HANDLE, query, &properties, &output);
    assert(queries == 1 && mpc_export_image_supported(result, &properties, &output, 1280, 720));
    assert(!mpc_export_image_supported(VK_ERROR_FORMAT_NOT_SUPPORTED, &properties, &output, 1280, 720));
    assert(!mpc_export_image_supported(VK_ERROR_DEVICE_LOST, &properties, &output, 1280, 720));
    output.externalMemoryProperties.externalMemoryFeatures = VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT;
    assert(!mpc_export_image_supported(result, &properties, &output, 1280, 720));
    output.externalMemoryProperties.externalMemoryFeatures = VK_EXTERNAL_MEMORY_FEATURE_EXPORTABLE_BIT;
    output.externalMemoryProperties.compatibleHandleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_OPAQUE_FD_BIT;
    assert(!mpc_export_image_supported(result, &properties, &output, 1280, 720));
    output.externalMemoryProperties.compatibleHandleTypes = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT;
    assert(!mpc_export_image_supported(result, &properties, &output, 1281, 720));
    assert(!mpc_export_image_supported(result, &properties, &output, 1280, 721));
    properties.imageFormatProperties.sampleCounts = VK_SAMPLE_COUNT_4_BIT;
    assert(!mpc_export_image_supported(result, &properties, &output, 1280, 720));
    puts("IMAGE_FORMAT_CONTRACT_OK: explicit modifier query and seven capability rejections; no GPU pass");
    return 0;
}

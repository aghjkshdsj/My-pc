/* Linux Vulkan offscreen graphics diagnostic, not presentation or game FPS. */
#include <vulkan/vulkan.h>
#include "renderer_classification.h"
#include <inttypes.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include "../Engine/ImagePixelContract.h"
#ifdef MPC_MOVING_SEQUENCE
#include "../Engine/MovingFrameContract.h"
#define MPC_RENDER_PHASE_COUNT MPC_MOVING_FRAMES
#elif defined(MPC_FRAME_SEQUENCE)
#include "../Engine/FrameSequenceContract.h"
#define MPC_RENDER_PHASE_COUNT MPC_FRAME_COUNT
#else
#define MPC_RENDER_PHASE_COUNT 2
#endif
#ifdef MPC_IMAGE_SCANOUT
#define MPC_RENDER_FORMAT VK_FORMAT_B8G8R8A8_UNORM
#define MPC_RENDER_BGRA 1
#else
#define MPC_RENDER_FORMAT VK_FORMAT_R8G8B8A8_UNORM
#define MPC_RENDER_BGRA 0
#endif

/* The native adapter supplies a private receipt stream. Linux keeps stdout. */
#ifndef MPC_VK_DIAGNOSTIC_STREAM
#define MPC_VK_DIAGNOSTIC_STREAM stdout
#endif
#ifndef MPC_VK_DIAGNOSTIC_PREFIX
#define MPC_VK_DIAGNOSTIC_PREFIX "MPC_VK_DIAGNOSTIC "
#endif
static void receipt_printf(const char *format, ...) {
    va_list arguments;
    va_start(arguments, format);
    vfprintf(MPC_VK_DIAGNOSTIC_STREAM, format, arguments);
    va_end(arguments);
}
static void receipt_putc(int value) { fputc(value, MPC_VK_DIAGNOSTIC_STREAM); }

enum { WIDTH = 1280, HEIGHT = 720, BYTES = WIDTH * HEIGHT * 4 };
static atomic_uint validation_errors;
#define VK_CHECK(call) do { VkResult r_ = (call); if (r_ != VK_SUCCESS) { \
    fprintf(stderr, "Vulkan call failed: %s = %d\n", #call, r_); exit(3); } } while (0)

static VKAPI_ATTR VkBool32 VKAPI_CALL validation(
    VkDebugUtilsMessageSeverityFlagBitsEXT severity, VkDebugUtilsMessageTypeFlagsEXT type,
    const VkDebugUtilsMessengerCallbackDataEXT *data, void *user) {
    (void)type; (void)user;
    if (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) atomic_fetch_add(&validation_errors, 1);
    fprintf(stderr, "VK_VALIDATION %s\n", data->pMessage);
    return VK_FALSE;
}
static void json_string(const char *value) {
    receipt_putc('"');
    for (const unsigned char *p = (const unsigned char *)value; *p; ++p) {
        if (*p == '"' || *p == '\\') receipt_printf("\\%c", *p);
        else if (*p < 32) receipt_printf("\\u%04x", *p);
        else receipt_putc(*p);
    }
    receipt_putc('"');
}
static int software(const VkPhysicalDeviceProperties *p) {
    return p->deviceType == VK_PHYSICAL_DEVICE_TYPE_CPU || mpc_renderer_is_software(p->deviceName);
}
static uint32_t memory_type(const VkPhysicalDeviceMemoryProperties *p, uint32_t bits,
                            VkMemoryPropertyFlags required, VkMemoryPropertyFlags preferred) {
    for (unsigned pass = 0; pass < 2; ++pass) for (uint32_t i = 0; i < p->memoryTypeCount; ++i) {
        VkMemoryPropertyFlags flags = p->memoryTypes[i].propertyFlags;
        if ((bits & (1u << i)) && (flags & required) == required &&
            (pass || (flags & preferred) == preferred)) return i;
    }
    fprintf(stderr, "No compatible memory type for flags %u\n", required); exit(4);
}
static VkShaderModule shader(VkDevice device, const char *path) {
    FILE *file = fopen(path, "rb");
    if (!file || fseek(file, 0, SEEK_END)) { perror(path); exit(5); }
    long length = ftell(file);
    if (length < 20 || length > 1024 * 1024 || length % 4 || fseek(file, 0, SEEK_SET)) exit(5);
    uint32_t *code = malloc((size_t)length);
    if (!code || fread(code, 1, (size_t)length, file) != (size_t)length || code[0] != 0x07230203u) exit(5);
    fclose(file);
    VkShaderModuleCreateInfo info = { .sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,
        .codeSize = (size_t)length, .pCode = code };
    VkShaderModule result; VK_CHECK(vkCreateShaderModule(device, &info, NULL, &result));
    free(code); return result;
}
#ifdef MPC_IMAGE_SCANOUT
#ifdef MPC_MOVING_SEQUENCE
#include "moving_scanout.h"
#else
#include "image_scanout.h"
#endif
#endif
int main(int argc, char **argv) {
    if (argc < 3 || argc > 5) {
        fprintf(stderr, "usage: vk-gate vertex.spv fragment.spv [--allow-software-diagnostic] [--require-validation]\n");
        return 2;
    }
    int diagnostic = 0, require_validation = 0;
    for (int i = 3; i < argc; ++i) {
        if (!strcmp(argv[i], "--allow-software-diagnostic")) diagnostic = 1;
        else if (!strcmp(argv[i], "--require-validation")) require_validation = 1;
        else return 2;
    }
    uint32_t layer_count = 0, instance_ext_count = 0;
    VK_CHECK(vkEnumerateInstanceLayerProperties(&layer_count, NULL));
    VkLayerProperties *layers = calloc(layer_count + 1, sizeof(*layers));
    if (!layers) return 4;
    VK_CHECK(vkEnumerateInstanceLayerProperties(&layer_count, layers));
    int has_validation = 0;
    for (uint32_t i = 0; i < layer_count; ++i)
        has_validation |= !strcmp(layers[i].layerName, "VK_LAYER_KHRONOS_validation");
    free(layers);
    VK_CHECK(vkEnumerateInstanceExtensionProperties(NULL, &instance_ext_count, NULL));
    VkExtensionProperties *instance_exts = calloc(instance_ext_count + 1, sizeof(*instance_exts));
    if (!instance_exts) return 4;
    VK_CHECK(vkEnumerateInstanceExtensionProperties(NULL, &instance_ext_count, instance_exts));
    int has_debug = 0, has_portability = 0;
    for (uint32_t i = 0; i < instance_ext_count; ++i) {
        has_debug |= !strcmp(instance_exts[i].extensionName, VK_EXT_DEBUG_UTILS_EXTENSION_NAME);
        has_portability |= !strcmp(instance_exts[i].extensionName, VK_KHR_PORTABILITY_ENUMERATION_EXTENSION_NAME);
    }
    free(instance_exts);
    int has_validation_features = 0;
    if (has_validation) {
        uint32_t count = 0;
        VK_CHECK(vkEnumerateInstanceExtensionProperties("VK_LAYER_KHRONOS_validation", &count, NULL));
        VkExtensionProperties *extensions = calloc(count + 1, sizeof(*extensions));
        if (!extensions) return 4;
        VK_CHECK(vkEnumerateInstanceExtensionProperties("VK_LAYER_KHRONOS_validation", &count, extensions));
        for (uint32_t i = 0; i < count; ++i)
            has_validation_features |= !strcmp(extensions[i].extensionName, VK_EXT_VALIDATION_FEATURES_EXTENSION_NAME);
        free(extensions);
    }
    if (require_validation && (!has_validation || !has_debug || !has_validation_features)) {
        fprintf(stderr, "Required validation layer/debug extension unavailable\n"); return 6;
    }
    int validated = has_validation && has_debug && has_validation_features;
    const char *layer_names[] = { "VK_LAYER_KHRONOS_validation" };
    const char *instance_names[3]; uint32_t enabled_instance_count = 0;
    if (validated) instance_names[enabled_instance_count++] = VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
    if (validated) instance_names[enabled_instance_count++] = VK_EXT_VALIDATION_FEATURES_EXTENSION_NAME;
    if (has_portability) instance_names[enabled_instance_count++] = VK_KHR_PORTABILITY_ENUMERATION_EXTENSION_NAME;
    VkDebugUtilsMessengerCreateInfoEXT debug_info = {
        .sType = VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
        .messageSeverity = VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT,
        .messageType = VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT | VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT |
                       VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT,
        .pfnUserCallback = validation };
    VkValidationFeatureEnableEXT sync_validation = VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT;
    VkValidationFeaturesEXT validation_features = { .sType = VK_STRUCTURE_TYPE_VALIDATION_FEATURES_EXT,
        .pNext = &debug_info, .enabledValidationFeatureCount = 1, .pEnabledValidationFeatures = &sync_validation };
    VkApplicationInfo app = { .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "My-pc Linux Vulkan gate", .apiVersion = VK_API_VERSION_1_1 };
    VkInstanceCreateInfo instance_info = { .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pNext = validated ? &validation_features : NULL, .pApplicationInfo = &app,
        .flags = has_portability ? VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR : 0,
        .enabledLayerCount = validated ? 1 : 0, .ppEnabledLayerNames = layer_names,
        .enabledExtensionCount = enabled_instance_count, .ppEnabledExtensionNames = instance_names };
    VkInstance instance; VK_CHECK(vkCreateInstance(&instance_info, NULL, &instance));
    VkDebugUtilsMessengerEXT messenger = VK_NULL_HANDLE;
    if (validated) {
        PFN_vkCreateDebugUtilsMessengerEXT create_debug =
            (PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance, "vkCreateDebugUtilsMessengerEXT");
        if (!create_debug) return 6;
        VK_CHECK(create_debug(instance, &debug_info, NULL, &messenger));
    }
    uint32_t device_count = 0; VK_CHECK(vkEnumeratePhysicalDevices(instance, &device_count, NULL));
    if (!device_count) return 6;
    VkPhysicalDevice *devices = calloc(device_count, sizeof(*devices));
    if (!devices) return 4;
    VK_CHECK(vkEnumeratePhysicalDevices(instance, &device_count, devices));
    /* CI restricts the ICD; a later guest receipt must record this chosen device. */
    VkPhysicalDevice physical = devices[0]; free(devices);
    VkPhysicalDeviceProperties props; vkGetPhysicalDeviceProperties(physical, &props);
    int fallback = software(&props);
    if (fallback && !diagnostic) {
        printf("MPC_VK_REJECTED software_renderer=%s\n", props.deviceName); return 20;
    }
    VkPhysicalDeviceFeatures features; vkGetPhysicalDeviceFeatures(physical, &features);
    VkPhysicalDeviceMemoryProperties memory; vkGetPhysicalDeviceMemoryProperties(physical, &memory);
    VkFormatProperties format; vkGetPhysicalDeviceFormatProperties(physical, MPC_RENDER_FORMAT, &format);
    if (!(format.optimalTilingFeatures & VK_FORMAT_FEATURE_COLOR_ATTACHMENT_BIT) ||
        !(format.optimalTilingFeatures & VK_FORMAT_FEATURE_TRANSFER_SRC_BIT)) return 6;
    uint32_t queue_count = 0; vkGetPhysicalDeviceQueueFamilyProperties(physical, &queue_count, NULL);
    VkQueueFamilyProperties *families = calloc(queue_count + 1, sizeof(*families));
    if (!families) return 4;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &queue_count, families);
    uint32_t family = UINT32_MAX;
    for (uint32_t i = 0; i < queue_count; ++i)
        if (families[i].queueCount && (families[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)) { family = i; break; }
    free(families); if (family == UINT32_MAX) return 6;
    uint32_t ext_count = 0; VK_CHECK(vkEnumerateDeviceExtensionProperties(physical, NULL, &ext_count, NULL));
    VkExtensionProperties *exts = calloc(ext_count + 1, sizeof(*exts));
    if (!exts) return 4;
    VK_CHECK(vkEnumerateDeviceExtensionProperties(physical, NULL, &ext_count, exts));
    const char *device_names[4]; uint32_t enabled_device_count = 0;
    for (uint32_t i = 0; i < ext_count; ++i)
        if (!strcmp(exts[i].extensionName, "VK_KHR_portability_subset"))
            device_names[enabled_device_count++] = "VK_KHR_portability_subset";
#ifdef MPC_IMAGE_SCANOUT
    if (image_extensions(physical, exts, ext_count, device_names, &enabled_device_count)) return 21;
#endif
    float priority = 1.0f;
    VkDeviceQueueCreateInfo queue_info = { .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority };
    VkDeviceCreateInfo device_info = { .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1, .pQueueCreateInfos = &queue_info,
        .enabledExtensionCount = enabled_device_count, .ppEnabledExtensionNames = device_names };
    VkDevice device; VK_CHECK(vkCreateDevice(physical, &device_info, NULL, &device));
    VkQueue queue; vkGetDeviceQueue(device, family, 0, &queue);
#ifdef MPC_IMAGE_SCANOUT
    if (image_allocate(device, &memory)) return 21;
#endif
    VkImageCreateInfo image_info = { .sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,
        .imageType = VK_IMAGE_TYPE_2D, .format = MPC_RENDER_FORMAT,
        .extent = { WIDTH, HEIGHT, 1 }, .mipLevels = 1, .arrayLayers = 1,
        .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
        .usage = VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT,
        .sharingMode = VK_SHARING_MODE_EXCLUSIVE, .initialLayout = VK_IMAGE_LAYOUT_UNDEFINED };
    VkImage image; VK_CHECK(vkCreateImage(device, &image_info, NULL, &image));
    VkMemoryRequirements requirements; vkGetImageMemoryRequirements(device, image, &requirements);
    VkMemoryAllocateInfo allocate = { .sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,
        .allocationSize = requirements.size, .memoryTypeIndex = memory_type(&memory, requirements.memoryTypeBits, 0,
                                                                          VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT) };
    VkDeviceMemory image_memory; VK_CHECK(vkAllocateMemory(device, &allocate, NULL, &image_memory));
    VK_CHECK(vkBindImageMemory(device, image, image_memory, 0));
    VkImageSubresourceRange range = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1 };
    VkImageViewCreateInfo view_info = { .sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,
        .image = image, .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = MPC_RENDER_FORMAT, .subresourceRange = range };
    VkImageView view; VK_CHECK(vkCreateImageView(device, &view_info, NULL, &view));
    VkBufferCreateInfo buffer_info = { .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
        .size = BYTES, .usage = VK_BUFFER_USAGE_TRANSFER_DST_BIT, .sharingMode = VK_SHARING_MODE_EXCLUSIVE };
    VkBuffer buffer; VK_CHECK(vkCreateBuffer(device, &buffer_info, NULL, &buffer));
    vkGetBufferMemoryRequirements(device, buffer, &requirements);
    uint32_t buffer_type = memory_type(&memory, requirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT,
                                    VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    allocate.allocationSize = requirements.size; allocate.memoryTypeIndex = buffer_type;
    VkDeviceMemory buffer_memory; VK_CHECK(vkAllocateMemory(device, &allocate, NULL, &buffer_memory));
    VK_CHECK(vkBindBufferMemory(device, buffer, buffer_memory, 0));
    VkAttachmentDescription attachment = { .format = MPC_RENDER_FORMAT, .samples = VK_SAMPLE_COUNT_1_BIT,
        .loadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE, .storeOp = VK_ATTACHMENT_STORE_OP_STORE,
        .stencilLoadOp = VK_ATTACHMENT_LOAD_OP_DONT_CARE, .stencilStoreOp = VK_ATTACHMENT_STORE_OP_DONT_CARE,
        .initialLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL, .finalLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
    VkAttachmentReference reference = { 0, VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL };
    VkSubpassDescription subpass = { .pipelineBindPoint = VK_PIPELINE_BIND_POINT_GRAPHICS,
        .colorAttachmentCount = 1, .pColorAttachments = &reference };
    VkRenderPassCreateInfo render_info = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,
        .attachmentCount = 1, .pAttachments = &attachment, .subpassCount = 1, .pSubpasses = &subpass };
    VkRenderPass render; VK_CHECK(vkCreateRenderPass(device, &render_info, NULL, &render));
    VkFramebufferCreateInfo frame_info = { .sType = VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,
        .renderPass = render, .attachmentCount = 1, .pAttachments = &view, .width = WIDTH, .height = HEIGHT, .layers = 1 };
    VkFramebuffer frame; VK_CHECK(vkCreateFramebuffer(device, &frame_info, NULL, &frame));
    VkShaderModule vertex = shader(device, argv[1]), fragment = shader(device, argv[2]);
    VkPipelineShaderStageCreateInfo stages[2] = {
        { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage = VK_SHADER_STAGE_VERTEX_BIT,
          .module = vertex, .pName = "main" },
        { .sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO, .stage = VK_SHADER_STAGE_FRAGMENT_BIT,
          .module = fragment, .pName = "main" } };
    VkPushConstantRange push = { VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(uint32_t) };
    VkPipelineLayoutCreateInfo layout_info = { .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .pushConstantRangeCount = 1, .pPushConstantRanges = &push };
    VkPipelineLayout layout; VK_CHECK(vkCreatePipelineLayout(device, &layout_info, NULL, &layout));
    VkPipelineVertexInputStateCreateInfo vertex_input = { .sType = VK_STRUCTURE_TYPE_PIPELINE_VERTEX_INPUT_STATE_CREATE_INFO };
    VkPipelineInputAssemblyStateCreateInfo assembly = { .sType = VK_STRUCTURE_TYPE_PIPELINE_INPUT_ASSEMBLY_STATE_CREATE_INFO,
        .topology = VK_PRIMITIVE_TOPOLOGY_TRIANGLE_LIST };
    VkViewport viewport = { 0, 0, WIDTH, HEIGHT, 0, 1 }; VkRect2D scissor = { { 0, 0 }, { WIDTH, HEIGHT } };
    VkPipelineViewportStateCreateInfo viewport_info = { .sType = VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,
        .viewportCount = 1, .pViewports = &viewport, .scissorCount = 1, .pScissors = &scissor };
    VkPipelineRasterizationStateCreateInfo raster = { .sType = VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,
        .polygonMode = VK_POLYGON_MODE_FILL, .cullMode = VK_CULL_MODE_NONE, .frontFace = VK_FRONT_FACE_COUNTER_CLOCKWISE, .lineWidth = 1 };
    VkPipelineMultisampleStateCreateInfo samples = { .sType = VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,
        .rasterizationSamples = VK_SAMPLE_COUNT_1_BIT };
    VkPipelineColorBlendAttachmentState blend = { .colorWriteMask = 15 };
    VkPipelineColorBlendStateCreateInfo blend_info = { .sType = VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,
        .attachmentCount = 1, .pAttachments = &blend };
    VkGraphicsPipelineCreateInfo pipeline_info = { .sType = VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,
        .stageCount = 2, .pStages = stages, .pVertexInputState = &vertex_input, .pInputAssemblyState = &assembly,
        .pViewportState = &viewport_info, .pRasterizationState = &raster, .pMultisampleState = &samples,
        .pColorBlendState = &blend_info, .layout = layout, .renderPass = render };
    VkPipeline pipeline; VK_CHECK(vkCreateGraphicsPipelines(device, VK_NULL_HANDLE, 1, &pipeline_info, NULL, &pipeline));
    VkCommandPoolCreateInfo pool_info = { .sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,
        .flags = VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT, .queueFamilyIndex = family };
    VkCommandPool pool; VK_CHECK(vkCreateCommandPool(device, &pool_info, NULL, &pool));
    VkCommandBufferAllocateInfo command_info = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1 };
    VkCommandBuffer command; VK_CHECK(vkAllocateCommandBuffers(device, &command_info, &command));
    VkFenceCreateInfo fence_info = { .sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO };
    VkFence fence; VK_CHECK(vkCreateFence(device, &fence_info, NULL, &fence));
    uint64_t mismatches = 0, checksum = 0;
    for (unsigned pass = 0; pass < MPC_RENDER_PHASE_COUNT; ++pass) {
#ifdef MPC_MOVING_SEQUENCE
        uint32_t phase = mpc_moving_phase(pass);
        int endpoint = mpc_moving_endpoint(pass);
        if (image_reacquire(device,queue,command,fence,pass,family)) return 21;
#elif defined(MPC_FRAME_SEQUENCE)
        uint32_t phase = mpc_frame_phase(pass);
#else
        uint32_t phase = pass ? 41 : 0;
#endif
        VK_CHECK(vkResetCommandBuffer(command, 0));
        VkCommandBufferBeginInfo begin = { .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
            .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT };
        VK_CHECK(vkBeginCommandBuffer(command, &begin));
        VkImageMemoryBarrier barrier = { .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .srcAccessMask = pass ? VK_ACCESS_TRANSFER_READ_BIT : 0, .dstAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,
            .oldLayout = pass ? VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL : VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = image, .subresourceRange = range };
        vkCmdPipelineBarrier(command, pass ? VK_PIPELINE_STAGE_TRANSFER_BIT : VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,
            VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, 0, 0, NULL, 0, NULL, 1, &barrier);
        VkRenderPassBeginInfo render_begin = { .sType = VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,
            .renderPass = render, .framebuffer = frame, .renderArea = scissor };
        vkCmdBeginRenderPass(command, &render_begin, VK_SUBPASS_CONTENTS_INLINE);
        vkCmdBindPipeline(command, VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
        vkCmdPushConstants(command, layout, VK_SHADER_STAGE_FRAGMENT_BIT, 0, sizeof(phase), &phase);
        vkCmdDraw(command, 3, 1, 0, 0); vkCmdEndRenderPass(command);
        barrier.srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT; barrier.dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT;
        barrier.oldLayout = VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL; barrier.newLayout = VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL;
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT,
            0, 0, NULL, 0, NULL, 1, &barrier);
        VkBufferImageCopy copy = { .imageSubresource = { VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1 },
            .imageExtent = { WIDTH, HEIGHT, 1 } };
#ifdef MPC_MOVING_SEQUENCE
        if (endpoint)
#endif
        vkCmdCopyImageToBuffer(command, image, VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL, buffer, 1, &copy);
#ifdef MPC_IMAGE_SCANOUT
        image_copy(command, image, pass, family);
#endif
        VkBufferMemoryBarrier host = { .sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER,
            .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT, .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED, .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .buffer = buffer, .offset = 0, .size = VK_WHOLE_SIZE };
#ifdef MPC_MOVING_SEQUENCE
        if (endpoint)
#endif
        vkCmdPipelineBarrier(command, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT,
            0, 0, NULL, 1, &host, 0, NULL);
        VK_CHECK(vkEndCommandBuffer(command)); VK_CHECK(vkResetFences(device, 1, &fence));
        VkSubmitInfo submit = { .sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &command };
        VK_CHECK(vkQueueSubmit(queue, 1, &submit, fence));
        VK_CHECK(vkWaitForFences(device, 1, &fence, VK_TRUE, UINT64_C(30000000000)));
#ifdef MPC_MOVING_SEQUENCE
        if (endpoint) {
#endif
        void *mapped; VK_CHECK(vkMapMemory(device, buffer_memory, 0, VK_WHOLE_SIZE, 0, &mapped));
        VkMappedMemoryRange invalidate = { .sType = VK_STRUCTURE_TYPE_MAPPED_MEMORY_RANGE,
            .memory = buffer_memory, .offset = 0, .size = VK_WHOLE_SIZE };
        VK_CHECK(vkInvalidateMappedMemoryRanges(device, 1, &invalidate));
        const unsigned char *pixels = mapped;
        for (unsigned y = 0; y < HEIGHT; ++y) for (unsigned x = 0; x < WIDTH; ++x) {
            const unsigned char *p = pixels + (y * WIDTH + x) * 4;
#ifdef MPC_MOVING_SEQUENCE
            mismatches += !mpc_moving_pattern_matches(p,x,y,phase,MPC_RENDER_BGRA);
#elif defined(MPC_FRAME_SEQUENCE)
            mismatches += !mpc_frame_pattern_matches(p, x, y, phase, MPC_RENDER_BGRA);
#else
            mismatches += !mpc_pattern_matches(p, x, y, phase, MPC_RENDER_BGRA);
#endif
            checksum += p[0] + p[1] + p[2] + p[3];
        }
        vkUnmapMemory(device, buffer_memory);
#ifdef MPC_MOVING_SEQUENCE
        }
#endif
#ifdef MPC_IMAGE_SCANOUT
        if (mismatches || atomic_load(&validation_errors)) return image_reject("guest-shader-pixels", 7);
        if (image_install(device, pass, phase)) return 21;
#endif
    }
#ifdef MPC_IMAGE_SCANOUT
#ifdef MPC_MOVING_SEQUENCE
    if (image_cleanup(device,queue,command,fence,family)) return 21;
#else
    if (image_cleanup(device)) return 21;
#endif
#endif
    VK_CHECK(vkDeviceWaitIdle(device));
    vkDestroyFence(device, fence, NULL); vkDestroyCommandPool(device, pool, NULL);
    vkDestroyPipeline(device, pipeline, NULL); vkDestroyPipelineLayout(device, layout, NULL);
    vkDestroyShaderModule(device, vertex, NULL); vkDestroyShaderModule(device, fragment, NULL);
    vkDestroyFramebuffer(device, frame, NULL); vkDestroyRenderPass(device, render, NULL);
    vkDestroyImageView(device, view, NULL); vkDestroyImage(device, image, NULL); vkFreeMemory(device, image_memory, NULL);
    vkDestroyBuffer(device, buffer, NULL); vkFreeMemory(device, buffer_memory, NULL); vkDestroyDevice(device, NULL);
    struct utsname machine; if (uname(&machine)) return 6;
    receipt_printf(MPC_VK_DIAGNOSTIC_PREFIX "{\"machine\":"); json_string(machine.machine);
    receipt_printf(",\"renderer\":"); json_string(props.deviceName);
    receipt_printf(",\"api_version\":%u,\"driver_version\":%u,\"vendor_id\":%u,\"device_id\":%u,\"device_type\":%u,"
           "\"software\":%s,\"width\":%u,\"height\":%u,\"pixels_checked\":%u,\"shader_phases\":%u,"
           "\"mismatches\":%" PRIu64 ",\"channel_sum\":%" PRIu64 ",\"validation_enabled\":%s,\"synchronization_validation_requested\":%s,"
           "\"validation_errors\":%u,\"queue_family\":%u,\"rgba8_optimal_features\":%u,\"readback_memory_flags\":%u,"
           "\"limits\":{\"maxImageDimension2D\":%u,\"maxMemoryAllocationCount\":%u,\"nonCoherentAtomSize\":%" PRIu64 "},"
           "\"features\":{\"geometryShader\":%s,\"tessellationShader\":%s,\"multiDrawIndirect\":%s,\"samplerAnisotropy\":%s},\"device_extensions\":[",
           props.apiVersion, props.driverVersion, props.vendorID, props.deviceID, props.deviceType,
           fallback ? "true" : "false", WIDTH, HEIGHT, WIDTH * HEIGHT *
#ifdef MPC_MOVING_SEQUENCE
           2,
#else
           MPC_RENDER_PHASE_COUNT,
#endif
           MPC_RENDER_PHASE_COUNT, mismatches, checksum,
           validated ? "true" : "false", validated ? "true" : "false", atomic_load(&validation_errors), family,
           format.optimalTilingFeatures, memory.memoryTypes[buffer_type].propertyFlags,
           props.limits.maxImageDimension2D, props.limits.maxMemoryAllocationCount, (uint64_t)props.limits.nonCoherentAtomSize,
           features.geometryShader ? "true" : "false", features.tessellationShader ? "true" : "false",
           features.multiDrawIndirect ? "true" : "false", features.samplerAnisotropy ? "true" : "false");
    for (uint32_t i = 0; i < ext_count; ++i) { if (i) receipt_putc(','); json_string(exts[i].extensionName); }
    receipt_printf("],\"metal_host_verified\":false,\"presentation_verified\":false,\"game_fps_verified\":false}\n");
    free(exts);
    if (validated) {
        PFN_vkDestroyDebugUtilsMessengerEXT destroy_debug =
            (PFN_vkDestroyDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance, "vkDestroyDebugUtilsMessengerEXT");
        destroy_debug(instance, messenger, NULL);
    }
    vkDestroyInstance(instance, NULL);
    if (fflush(MPC_VK_DIAGNOSTIC_STREAM) || ferror(MPC_VK_DIAGNOSTIC_STREAM)) return 8;
    return mismatches || atomic_load(&validation_errors) ? 7 : 0;
}

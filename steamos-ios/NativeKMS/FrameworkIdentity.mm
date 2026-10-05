#import "Bridge.h"
#include <CommonCrypto/CommonDigest.h>
#include <dlfcn.h>
#include <mach-o/loader.h>
#include <mach/machine.h>
#include <string.h>


static NSString *digest(NSData *data) {
    unsigned char value[CC_SHA256_DIGEST_LENGTH];
    CC_SHA256(data.bytes, static_cast<CC_LONG>(data.length), value);
    NSMutableString *text = [NSMutableString string];
    for (unsigned char byte : value) [text appendFormat:@"%02x", byte];
    return text;
}
static NSDictionary *textSection(NSData *data) {
    if (data.length < sizeof(mach_header_64)) return nil;
    const auto *header = static_cast<const mach_header_64 *>(data.bytes);
    if (header->magic != MH_MAGIC_64 || header->cputype != CPU_TYPE_ARM64 || header->filetype != MH_DYLIB ||
        header->ncmds > 1024 || sizeof(*header) + static_cast<uint64_t>(header->sizeofcmds) > data.length) return nil;
    const auto *bytes = static_cast<const uint8_t *>(data.bytes);
    uint64_t cursor = sizeof(*header), end = cursor + header->sizeofcmds;
    NSDictionary *found = nil;
    BOOL ios = NO;
    for (uint32_t i = 0; i < header->ncmds; ++i) {
        if (cursor + sizeof(load_command) > end) return nil;
        const auto *command = reinterpret_cast<const load_command *>(bytes + cursor);
        if (command->cmdsize < sizeof(load_command) || cursor + command->cmdsize > end) return nil;
        if (command->cmd == LC_BUILD_VERSION) {
            if (command->cmdsize < sizeof(build_version_command)) return nil;
            ios = reinterpret_cast<const build_version_command *>(command)->platform == 2;
        }
        if (command->cmd == LC_SEGMENT_64) {
            if (command->cmdsize < sizeof(segment_command_64)) return nil;
            const auto *segment = reinterpret_cast<const segment_command_64 *>(command);
            if (segment->nsects > 1024 || sizeof(*segment) + static_cast<uint64_t>(segment->nsects) * sizeof(section_64) > command->cmdsize) return nil;
            const auto *sections = reinterpret_cast<const section_64 *>(bytes + cursor + sizeof(*segment));
            for (uint32_t index = 0; index < segment->nsects; ++index) {
                const auto &section = sections[index];
                if (strncmp(section.sectname, "__text", 16) || strncmp(section.segname, "__TEXT", 16)) continue;
                if (found || !section.size || section.offset < end || section.size > data.length || section.offset > data.length - section.size) return nil;
                NSData *code = [data subdataWithRange:NSMakeRange(section.offset, static_cast<NSUInteger>(section.size))];
                found = @{@"bytes": @(section.size), @"sha256": digest(code)};
            }
        }
        cursor += command->cmdsize;
    }
    return ios ? found : nil;
}
NSDictionary *MPCFrameworkTextIdentity(NSString *path) {
    NSData *data = [NSData dataWithContentsOfFile:path options:NSDataReadingMappedIfSafe error:nil];
    return data ? textSection(data) : nil;
}

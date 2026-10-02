#!/usr/bin/env python3
"""Repair public-SDK diagnostics and fixed-base PE placement in locked Wine."""
from pathlib import Path


def replace_once(source, before, after, label):
    if source.count(before) != 1:
        raise ValueError(f'{label}: expected exactly one locked source marker')
    return source.replace(before, after, 1)


def repair_virtual_source(source):
    # Dokimon.exe is only 0xa88000 bytes, but its PE characteristics are
    # 0x23 (RELOCS_STRIPPED). The old size floor kept its 0x140000000
    # reservation closed, so Wine moved it and then failed with c0000018.
    # Only the image mapper knows this property; anonymous allocations must
    # retain their existing size floor and cannot claim a small image's base.
    source = replace_once(source,
        'static int ios_exe_win_claim( const void *addr, size_t size )',
        'static int ios_exe_win_claim( const void *addr, size_t size, int fixed_main )',
        'fixed-base claim signature')
    source = replace_once(source,
        '    if (a < ios_exe_win_base || a + size > ios_exe_win_base + ios_exe_win_size) return 0;\n'
        '    if (size < 64u * 1024u * 1024u)',
        '    if (!size || a < ios_exe_win_base || a - ios_exe_win_base >= ios_exe_win_size ||\n'
        '        size > ios_exe_win_size - (a - ios_exe_win_base)) return 0;\n'
        '    if (size < 64u * 1024u * 1024u && !fixed_main)',
        'fixed-base bounds and small-image floor')
    source = replace_once(source,
        '    ios_exe_win_claim( start, size );   /* ml977: hand over the window if this is the one */',
        '    ios_exe_win_claim( start, size, 0 );   /* anonymous requests retain the size floor */',
        'anonymous fixed mapping')
    marker = 'static NTSTATUS map_image_view( struct file_view **view_ret, struct pe_image_info *image_info, SIZE_T size,'
    policy = '''/* My-pc: a small fixed-base x64 executable must not be mistaken for a
 * relocatable image. Keep Wine DLLs, builtins, WoW64 windows and alternate
 * mapping addresses on the original path. Reservation ownership, retirement,
 * no-overwrite mapping and claim rollback remain in the existing helpers. */
static BOOL ios_exe_win_fixed_main( const struct pe_image_info *info, const void *base,
                                   BOOL is_builtin, BOOL wow_image )
{
    return !is_builtin && !wow_image && base &&
           info->machine == IMAGE_FILE_MACHINE_AMD64 &&
           (info->image_charact & IMAGE_FILE_RELOCS_STRIPPED) &&
           !(info->image_charact & IMAGE_FILE_DLL) &&
           (uintptr_t)base == info->base;
}

'''
    source = replace_once(source, marker, policy + marker, 'fixed-image policy')
    source = replace_once(source,
        '    if (base)\n    {\n'
        '        status = map_view( view_ret, base, size, alloc_type, vprot, limit_low, limit_high, 0 );',
        '    if (base)\n    {\n'
        '        if (ios_exe_win_fixed_main( image_info, base, is_builtin, wow_image ))\n'
        '        {\n'
        '            int granted = ios_exe_win_claim( base, size, 1 );\n'
        '            dprintf( 2, "[mypc-fixed-image] base=%p size=%#lx claim=%d stripped=1\\n",\n'
        '                     base, (unsigned long)size, granted );\n'
        '        }\n'
        '        status = map_view( view_ret, base, size, alloc_type, vprot, limit_low, limit_high, 0 );',
        'preferred image mapping')
    source = replace_once(source,
        '"the window can be re-granted to the next >=64MB fixed map\\n",',
        '"the window can be re-granted to the next eligible fixed image\\n",',
        'retirement diagnostic')
    return source


def repair_server_source(source):
    # The public iOS SDK has no ri_page_wait_time_mach member. State that the
    # optional trace field is unavailable instead of emitting a made-up zero.
    source = replace_once(source,
        'XP_MS( ru.ri_page_wait_time_mach - pru.ri_page_wait_time_mach ),',
        '', 'optional page-wait measurement')
    return replace_once(source, 'pgw=%.1f', 'pgw=unavailable', 'page-wait label')


def main(root=Path('.')):
    server = root / 'build/ntdll-unix/server_ios.c'
    virtual = root / 'build/ntdll-unix/virtual_ios.c'
    # Preflight both complete transformations before modifying either file.
    server_source = repair_server_source(server.read_text(encoding='utf-8'))
    virtual_source = repair_virtual_source(virtual.read_text(encoding='utf-8'))
    server.write_text(server_source, encoding='utf-8')
    virtual.write_text(virtual_source, encoding='utf-8')


if __name__ == '__main__':
    main()

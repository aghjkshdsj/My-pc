#!/usr/bin/env python3
"""Scoped Darwin app-private fd backing; no graphics success override."""
import difflib
import hashlib
import pathlib
import shutil


def patch(source, output, project):
    path = source / 'src/mesa/util/anon_file.c'
    original = path.read_text(encoding='utf-8')
    assert 'MPC_GPU_ALLOC_FAIL' in original and 'MPC_GPU_PRIVATE_FILE' not in original
    assert original.count('#include "anon_file.h"') == 1
    changed = original.replace('#include "anon_file.h"',
        '#include "anon_file.h"\n#if defined(__APPLE__)\n#include "mpc_ios_private_file.h"\n#endif')
    start = changed.index('#elif defined(__APPLE__)\n') + len('#elif defined(__APPLE__)\n')
    end = changed.index('#elif defined(__OpenBSD__)\n', start)
    original_apple = changed[start:end]
    replacement = '''   const char *private_dir = getenv("MPC_GPU_SHM_DIR");
   if (private_dir && private_dir[0]) {
      fd = mpc_ios_private_file_open(private_dir);
      if (fd < 0) {
         const int saved = errno;
         fprintf(stderr, "MPC_GPU_PRIVATE_FILE_FAIL errno=%d bytes=%lld\\n", saved, (long long)size);
         errno = saved;
      } else {
         fprintf(stderr, "MPC_GPU_PRIVATE_FILE_OPENED bytes=%lld\\n", (long long)size);
      }
   } else {
''' + original_apple + '   }\n'
    changed = changed[:start] + replacement + changed[end:]
    path.write_text(changed, encoding='utf-8')
    helper = project / 'Engine/PrivateSharedFile.h'
    shutil.copyfile(helper, source / 'src/mesa/util/mpc_ios_private_file.h')
    shutil.copyfile(helper, output / 'PrivateSharedFile.h')
    shutil.copyfile(project / 'tests/RendererPrivateFileTests.c', output / 'RendererPrivateFileTests.c')
    diff = ''.join(difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True),
                                     fromfile='a/src/mesa/util/anon_file.c', tofile='b/src/mesa/util/anon_file.c'))
    (output / 'ios-private-shared-file.patch').write_text(diff, encoding='utf-8')
    return {'source_before_sha256': hashlib.sha256(original.encode()).hexdigest(),
            'source_after_sha256': hashlib.sha256(changed.encode()).hexdigest(),
            'helper_sha256': hashlib.sha256(helper.read_bytes()).hexdigest(),
            'allocator_policy_changed': True, 'explicit_app_private_directory_required': True,
            'atomic_exclusive_create': True, 'mode_0600': True, 'unlink_before_mapping': True,
            'close_on_exec': True, 'hosted_native_tests_passed': False,
            'phone_tested': False, 'host_memory_import_verified': False, 'success_override': False}

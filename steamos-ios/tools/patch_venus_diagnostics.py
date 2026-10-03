#!/usr/bin/env python3
"""Pinned failure diagnostics only; no allocator fallback or success override."""
import difflib
import hashlib
import json
import pathlib


def once(text, old, new):
    assert text.count(old) == 1, 'Pinned renderer diagnostic input changed'
    return text.replace(old, new)


def transform(name, text):
    assert 'MPC_GPU_' not in text, 'Diagnostics already applied'
    if name == 'src/mesa/util/anon_file.c':
        text = once(text, '#include <unistd.h>\n', '#include <unistd.h>\n\n'
            'static void mpc_allocator_failure(const char *stage, off_t size)\n'
            '{\n'
            '   const int saved = errno;\n'
            '   fprintf(stderr, "MPC_GPU_ALLOC_FAIL stage=%s errno=%d bytes=%lld\\n",\n'
            '           stage, saved, (long long)size);\n'
            '   errno = saved;\n'
            '}\n')
        text = once(text, '      errno = EINVAL;\n      return -1;',
            '      errno = EINVAL;\n      mpc_allocator_failure("group-name", size);\n      return -1;')
        text = once(text, '   if (fd < 0)\n      return -1;\n\n   ret = ftruncate(fd, size);',
            '   if (fd < 0) {\n      mpc_allocator_failure("anonymous-open", size);\n'
            '      return -1;\n   }\n\n   ret = ftruncate(fd, size);')
        return once(text, '   if (ret < 0) {\n      close(fd);\n      return -1;\n   }',
            '   if (ret < 0) {\n      const int saved = errno;\n'
            '      mpc_allocator_failure("ftruncate", size);\n      close(fd);\n'
            '      errno = saved;\n      return -1;\n   }')
    if name == 'src/venus/vkr_context.c':
        text = once(text, '#include <sys/types.h>\n', '#include <sys/types.h>\n#include <errno.h>\n#include <stdio.h>\n')
        text = once(text, '   int fd = os_create_anonymous_file(alloc_size, "vkr-shmem");\n'
            '   if (fd < 0)\n      return false;',
            '   int fd = os_create_anonymous_file(alloc_size, "vkr-shmem");\n'
            '   if (fd < 0) {\n      fprintf(stderr, "MPC_GPU_SHMEM_FAIL stage=anonymous-file errno=%d bytes=%llu\\n",\n'
            '              errno, (unsigned long long)alloc_size);\n      return false;\n   }')
        text = once(text, '   if (mmap_ptr == MAP_FAILED) {\n      close(fd);\n      return false;\n   }',
            '   if (mmap_ptr == MAP_FAILED) {\n      const int saved = errno;\n'
            '      fprintf(stderr, "MPC_GPU_SHMEM_FAIL stage=mmap errno=%d bytes=%llu\\n",\n'
            '              saved, (unsigned long long)alloc_size);\n      close(fd);\n'
            '      errno = saved;\n      return false;\n   }')
        return once(text, '                                             VIRGL_RESOURCE_FD_SHM, -1, mmap_ptr)) {\n'
            '      munmap(mmap_ptr, alloc_size);',
            '                                             VIRGL_RESOURCE_FD_SHM, -1, mmap_ptr)) {\n'
            '      fprintf(stderr, "MPC_GPU_SHMEM_FAIL stage=resource-table bytes=%llu\\n",\n'
            '              (unsigned long long)alloc_size);\n      munmap(mmap_ptr, alloc_size);')
    if name == 'src/virglrenderer.c':
        text = once(text, '   ctx = virgl_context_lookup(args->ctx_id);\n   if (!ctx)\n      return -EINVAL;',
            '   ctx = virgl_context_lookup(args->ctx_id);\n   if (!ctx) {\n'
            '      fprintf(stderr, "MPC_GPU_BLOB_FAIL stage=context-lookup ctx=%u result=%d\\n",\n'
            '              args->ctx_id, -EINVAL);\n      return -EINVAL;\n   }')
        return once(text, '   ret = ctx->get_blob(ctx, args->res_handle, args->blob_id, args->size, args->blob_flags, &blob);\n'
            '   if (ret)\n      return ret;',
            '   ret = ctx->get_blob(ctx, args->res_handle, args->blob_id, args->size, args->blob_flags, &blob);\n'
            '   if (ret) {\n'
            '      fprintf(stderr, "MPC_GPU_BLOB_FAIL stage=get-blob ctx=%u result=%d blob=%llu bytes=%llu flags=%u\\n",\n'
            '              args->ctx_id, ret, (unsigned long long)args->blob_id,\n'
            '              (unsigned long long)args->size, args->blob_flags);\n      return ret;\n   }')
    raise AssertionError(name)


def patch(source, output):
    entries, diff = {}, []
    for name in ['src/mesa/util/anon_file.c', 'src/venus/vkr_context.c', 'src/virglrenderer.c']:
        path = source / name
        original = path.read_text(encoding='utf-8')
        changed = transform(name, original)
        path.write_text(changed, encoding='utf-8')
        entries[name] = {'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
                         'patched_sha256': hashlib.sha256(changed.encode()).hexdigest()}
        diff += list(difflib.unified_diff(original.splitlines(keepends=True), changed.splitlines(keepends=True),
                                        fromfile='a/' + name, tofile='b/' + name))
    (output / 'venus-failure-diagnostics.patch').write_text(''.join(diff), encoding='utf-8')
    return {'files': entries, 'failure_errno_and_stage_compiled': True,
            'allocator_policy_changed': False, 'success_override': False,
            'host_memory_import_verified': False, 'phone_tested': False}

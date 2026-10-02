#!/usr/bin/env python3
"""Actual missing-DRM-device test inside an ephemeral private mount namespace."""
import json
import os
import pathlib
import subprocess
import sys


def main():
    parent_namespace, executable, vertex, fragment, icd, libraries = sys.argv[1:]
    namespace = os.readlink('/proc/self/ns/mnt')
    assert namespace != parent_namespace, 'Never mount over the host device directory'
    devices = pathlib.Path('/dev/dri')
    if devices.exists():
        assert devices.is_dir() and not devices.is_symlink()
        subprocess.run(['mount', '-t', 'tmpfs', '-o', 'size=4k,mode=000', 'none', str(devices)], check=True)
    assert not devices.exists() or not list(devices.iterdir())
    environment = dict(os.environ, VK_DRIVER_FILES=icd, LD_LIBRARY_PATH=libraries)
    environment.pop('VN_DEBUG', None)
    result = subprocess.run([executable, vertex, fragment], env=environment,
                            capture_output=True, text=True, timeout=30)
    print(json.dumps({'scope': 'hosted-linux-private-namespace-missing-drm-device',
                      'parent_mount_namespace': parent_namespace, 'mount_namespace': namespace,
                      'drm_device_nodes': [], 'driver_files': icd, 'returncode': result.returncode,
                      'stdout': result.stdout, 'stderr': result.stderr,
                      'guest_kernel_tested': False, 'phone_tested': False, 'graphics_verified': False}))


if __name__ == '__main__':
    main()

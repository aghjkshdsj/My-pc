"""Build-audit rejection tests. Fixtures do not establish phone EGL/Metal."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from collect_gpu_engine_sources import audit_headless_backend, audit_thread_retirement
from patch_qemu_gpu import transform


class GPUBackendBuildTests(unittest.TestCase):
    def test_rcu_retirement_requires_actual_export_and_compilation(self):
        config = '#define CONFIG_SHARED_LIBRARY_BUILD 1\n'
        symbol = '00000000007c6160 T _rcu_unregister_thread\n'
        commands = [{'file': '../util/rcu.c', 'command': 'clang -c ../util/rcu.c -o rcu.o'}]
        result = audit_thread_retirement(config, symbol, commands)
        self.assertTrue(result['rcu_unregister_definition_exported'])
        self.assertFalse(result['host_unregister_executed'])
        self.assertFalse(result['phone_crash_fixed'])
        for bad in ('rcu_unregister_thread', '0000 t _rcu_unregister_thread\n', ' U _rcu_unregister_thread\n'):
            with self.assertRaises(AssertionError): audit_thread_retirement(config, bad, commands)
        with self.assertRaises(AssertionError): audit_thread_retirement('#undef CONFIG_SHARED_LIBRARY_BUILD', symbol, commands)
        with self.assertRaises(AssertionError): audit_thread_retirement(config, symbol, [])
        with self.assertRaises(AssertionError): audit_thread_retirement(config, symbol, [{'file': '../util/rcu.c', 'command': 'echo ../util/rcu.c'}])

    def test_enabled_backend_records_only_compilation(self):
        for config in ('#define CONFIG_PIXMAN\n', '#define CONFIG_PIXMAN 1\n'):
            result = audit_headless_backend(config, '000000 T _mpc_qemu_register_egl_headless\n',
                [{'file': '../ui/egl-headless.c', 'command': 'clang -c ../ui/egl-headless.c -o backend.o'}])
            self.assertTrue(result['egl_headless_builtin_compiled'])
            self.assertNotIn('metal_runtime_verified', result)

    def test_phone_failed_configuration_rejected(self):
        # Exact relevant configuration of the build that exited on the phone.
        config = '#define CONFIG_DARWIN\n#define CONFIG_EGL\n#define CONFIG_OPENGL\n#undef CONFIG_PIXMAN\n'
        with self.assertRaises(AssertionError):
            audit_headless_backend(config, '_mpc_qemu_register_egl_headless',
                [{'file': '../ui/egl-headless.c', 'command': 'clang -c ../ui/egl-headless.c'}])

    def test_strings_or_partial_objects_cannot_satisfy_backend(self):
        for config in ('#undef CONFIG_PIXMAN\n', '#define CONFIG_PIXMAN 0\n'):
            with self.assertRaises(AssertionError): audit_headless_backend(config, '_mpc_qemu_register_egl_headless', [])
        with self.assertRaises(AssertionError): audit_headless_backend('#define CONFIG_PIXMAN\n', 'egl-headless', [])
        with self.assertRaises(AssertionError): audit_headless_backend('#define CONFIG_PIXMAN\n', '_mpc_qemu_register_egl_headless', [])
        with self.assertRaises(AssertionError):
            audit_headless_backend('#define CONFIG_PIXMAN\n', '_mpc_qemu_register_egl_headless',
                [{'file': '../ui/egl-headless.c', 'command': 'echo ui/egl-headless.c'}])

    def test_registration_helper_requires_explicit_library_export(self):
        source='{\n    qemu_init;\n    qemu_cleanup;\n};\n'
        changed=transform('system/qemu.symbols',source)
        self.assertIn('    mpc_qemu_register_egl_headless;\n',changed)
        self.assertIn('    qemu_cleanup;\n',changed)
        with self.assertRaises(AssertionError): transform('system/qemu.symbols',changed)


if __name__ == '__main__':
    unittest.main()

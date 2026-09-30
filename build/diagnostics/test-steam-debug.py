"""Crash summaries keep an early PC despite long later mapping output."""
import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('crash', pathlib.Path(__file__).with_name('read-steam-debug.py'))
crash = importlib.util.module_from_spec(spec); spec.loader.exec_module(crash)


class DebuggerSummary(unittest.TestCase):
    def test_early_crash_and_mapping_are_retained_without_paths(self):
        content = '''Thread 1 received signal SIGSEGV, Segmentation fault.
MYPC_TCTI_GDB_PC=0x401234
#0  0x401234 in ?? ()
0x400000 0x410000 0x10000 0x0 r-xp /home/private-name/steamrtarm64/steam
''' + ('unrelated mapping line\n' * 2000) + 'MYPC_TCTI_GDB_FINISHED'
        summary = crash.summarize(content)
        self.assertEqual(summary['signals'], ['SIGSEGV'])
        self.assertEqual(summary['module'], {'name': 'steam', 'file_offset': '0x1234'})
        self.assertNotIn('private-name', str(summary))

    def test_no_inferior_is_not_a_captured_crash(self):
        summary = crash.summarize('ptrace: Operation not permitted\nNo registers.\nMYPC_TCTI_GDB_FINISHED')
        self.assertTrue(summary['ptrace_denied'])
        self.assertTrue(summary['no_registers'])
        self.assertIsNone(summary['pc'])
        self.assertEqual(summary['signals'], [])

    def test_versioned_system_library_and_each_frame_offset(self):
        content = '''Thread 1 received signal SIGSEGV, Segmentation fault.
MYPC_TCTI_GDB_PC=0x401234
#0  0x401234 in ?? () from /usr/lib/aarch64-linux-gnu/libSDL3.so.0.2.16
#1  0x500024 in other ()
0x400000 0x410000 0x10000 0x8000 r-xp /usr/lib/aarch64-linux-gnu/libSDL3.so.0.2.16
0x500000 0x510000 0x10000 0x0 r-xp /home/steam/.local/share/Steam/steamrtarm64/steam
MYPC_TCTI_GDB_CODE_BEGIN
0x401234: 0xf9400001 0xd503201f 0xd65f03c0 0xd4200000
MYPC_TCTI_GDB_CODE_END
MYPC_TCTI_GDB_FINISHED'''
        summary = crash.summarize(content)
        self.assertEqual(summary['module'], {'name': 'libSDL3.so.0.2.16', 'file_offset': '0x9234'})
        self.assertEqual(summary['frames'][1]['module'], {'name': 'steam', 'file_offset': '0x24'})
        self.assertEqual(len(summary['instruction_words']), 4)
        self.assertNotIn('/usr/lib', str(summary))

    def test_untrusted_library_and_nonexecutable_memory_are_not_dumped(self):
        for permissions, path in [('rw-p', '/usr/lib/aarch64-linux-gnu/libSDL3.so.0'),
                                  ('r-xp', '/home/private-name/libsecret.so.1'),
                                  ('r-xp', '/usr/lib/../private/libsecret.so.1')]:
            with self.subTest(path=path, permissions=permissions):
                content = f'''MYPC_TCTI_GDB_PC=0x401234
0x400000 0x410000 0x10000 0x0 {permissions} {path}
MYPC_TCTI_GDB_CODE_BEGIN
0x401234: 0xf9400001 0xd503201f 0xd65f03c0 0xd4200000
MYPC_TCTI_GDB_CODE_END
MYPC_TCTI_GDB_FINISHED'''
                summary = crash.summarize(content)
                self.assertEqual(summary['instruction_words'], [])
                self.assertNotIn('private', str(summary))

    def test_instruction_dump_at_another_address_is_rejected(self):
        content = '''MYPC_TCTI_GDB_PC=0x401234
0x400000 0x410000 0x10000 0x0 r-xp /lib/aarch64-linux-gnu/libc.so.6
MYPC_TCTI_GDB_CODE_BEGIN
0x401238: 0xf9400001 0xd503201f 0xd65f03c0 0xd4200000
MYPC_TCTI_GDB_CODE_END
MYPC_TCTI_GDB_FINISHED'''
        self.assertEqual(crash.summarize(content)['instruction_words'], [])


if __name__ == '__main__':
    unittest.main()

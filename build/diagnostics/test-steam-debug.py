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


if __name__ == '__main__':
    unittest.main()

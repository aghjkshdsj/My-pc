import pathlib, struct, sys, unittest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
from macho_exports import defined_export


def library(flags=15, first=0, count=1, address=4096):
    strings = b'\0_rcu_unregister_thread\0'
    commands = struct.pack('<6I', 2, 24, 136, 1, 152, len(strings))
    commands += struct.pack('<20I', 11, 80, 0, 0, first, count, *([0] * 14))
    header = struct.pack('<8I', 0xfeedfacf, 0x100000c, 0, 6, 2, len(commands), 0, 0)
    return header + commands + struct.pack('<IBBHQ', 1, flags, 1, 0, address) + strings


class ExportsTests(unittest.TestCase):
    def test_actual_definition_required(self):
        self.assertTrue(defined_export(library(), 'rcu_unregister_thread'))
        for flags in (30, 14, 1, 31):
            self.assertFalse(defined_export(library(flags=flags), 'rcu_unregister_thread'))
        self.assertFalse(defined_export(library(address=0), 'rcu_unregister_thread'))
        self.assertFalse(defined_export(library(count=0), 'rcu_unregister_thread'))
        self.assertFalse(defined_export(library(), 'unrelated'))

    def test_bounds_and_truncation(self):
        for changed in (library()[:-1], library(first=1, count=1), library()[:32], b'rcu_unregister_thread'):
            with self.assertRaises(ValueError): defined_export(changed, 'rcu_unregister_thread')


if __name__ == '__main__': unittest.main()

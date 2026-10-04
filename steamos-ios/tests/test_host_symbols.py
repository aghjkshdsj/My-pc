"""Reject corrupted or ambiguous symbol identities; synthetic fixtures only."""
import pathlib,struct,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from verify_host_symbols import macho_uuid

def fixture(kind=2,commands=None,cpu=0x100000c):
    commands=commands if commands is not None else [struct.pack('<II',0x1b,24)+bytes(range(16))]
    return struct.pack('<8I',0xfeedfacf,cpu,0,kind,len(commands),sum(map(len,commands)),0,0)+b''.join(commands)

class SymbolIdentityTests(unittest.TestCase):
    def test_exact_arm64_uuid(self):
        expected='00010203-0405-0607-0809-0A0B0C0D0E0F'
        self.assertEqual(macho_uuid(fixture(),2),expected)
        self.assertEqual(macho_uuid(fixture(10),10),expected)
    def test_truncated_corrupt_wrong_arch_and_filetype(self):
        data=fixture()
        for bad in [data[:i] for i in (0,31,32,39,55)]+[fixture(cpu=7),fixture(10)]:
            with self.subTest(size=len(bad)),self.assertRaises(ValueError):macho_uuid(bad,2)
    def test_missing_duplicate_zero_and_invalid_command(self):
        command=struct.pack('<II',0x1b,24)+bytes(range(16))
        for commands in [[],[command,command],[struct.pack('<II',0x1b,24)+bytes(16)],
                         [struct.pack('<II',0x1b,8)],[struct.pack('<II',0x1b,0)],
                         [struct.pack('<II',0x1b,100)+bytes(16)]]:
            with self.subTest(commands=len(commands)),self.assertRaises(ValueError):macho_uuid(fixture(commands=commands),2)
if __name__=='__main__':unittest.main()

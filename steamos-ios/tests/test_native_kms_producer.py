"""Separate standard producer derivation and explicit payload-addition boundaries."""
import hashlib
import pathlib
import stat
import sys
import tempfile
import unittest
PROJECT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'tools'))
from prepare_native_kms_guest import prepare,PINS
from build_guest_image_payload import extend_newc
from make_initramfs import record
class NativeKMSProducerTests(unittest.TestCase):
    def test_derivation_preserves_accepted_sources_and_removes_dwell_protocol(self):
        (PROJECT/'out').mkdir(exist_ok=True)
        before={n:(PROJECT/n).read_bytes() for n in PINS}
        with tempfile.TemporaryDirectory(dir=PROJECT/'out',prefix='native-kms-derive-') as d:
            output=pathlib.Path(d)/'generated';prepare(output)
            images=(output/'native_kms_images.h').read_text()
            self.assertNotIn('drmModeSetCrtc',images);self.assertNotIn('drmModeDirtyFB',images)
            self.assertNotIn('nanosleep',images);self.assertNotIn('frame_release_channel',images)
            self.assertIn('return native_present(target->framebuffer,pass);',images)
            self.assertIn('if (native_disable()) return 21;',images)
            self.assertIn('producer_fence_completed',images)
            with self.assertRaises(FileExistsError):prepare(output)
        self.assertEqual(before,{n:(PROJECT/n).read_bytes() for n in PINS})

    def test_new_binary_requires_named_opt_in_and_parent_records_are_unchanged(self):
        parent=record('init',stat.S_IFREG|0o755,b'old init',inode=1)+record('TRAILER!!!',0,b'',inode=2)
        replacements={'vk-native-kms-gate':(stat.S_IFREG|0o755,b'not a compiled fixture')}
        with self.assertRaises(AssertionError):extend_newc(parent,replacements)
        updated=extend_newc(parent,replacements,additions=('vk-native-kms-gate',))
        self.assertTrue(updated.startswith(record('init',stat.S_IFREG|0o755,b'old init',inode=1)))
        with self.assertRaises(AssertionError):extend_newc(parent,{'elsewhere':(stat.S_IFREG|0o755,b'x')},additions=('elsewhere',))
if __name__=='__main__':unittest.main()

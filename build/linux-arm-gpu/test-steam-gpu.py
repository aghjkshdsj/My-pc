"""Reject software fallback and incomplete Steam GPU evidence."""
import unittest
import pathlib
import sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'linux-arm'))
from steam_gpu import accelerated_state


class RendererEvidence(unittest.TestCase):
    def setUp(self):
        self.gpu = {'auxAttributes': {'glRenderer': 'ANGLE (virgl)'},
                    'featureStatus': {'gpu_compositing': 'enabled', 'webgl': 'enabled'}}
        self.webgl = {'available': True, 'renderer': 'virgl', 'pixel': [255, 0, 0, 255], 'error': 0}

    def test_complete_renderer_and_real_readback(self):
        self.assertTrue(accelerated_state(self.gpu, self.webgl))

    def test_software_fallback(self):
        for name in ('llvmpipe', 'softpipe', 'SwiftShader', 'software'):
            self.webgl['renderer'] = 'virgl ' + name
            self.assertFalse(accelerated_state(self.gpu, self.webgl))

    def test_disabled_compositing_and_bad_readback(self):
        self.gpu['featureStatus']['gpu_compositing'] = 'disabled_software'
        self.assertFalse(accelerated_state(self.gpu, self.webgl))
        self.gpu['featureStatus']['gpu_compositing'] = 'enabled'
        self.webgl['pixel'] = [0, 0, 0, 255]
        self.assertFalse(accelerated_state(self.gpu, self.webgl))

    def test_missing_evidence(self):
        self.assertFalse(accelerated_state({}, {}))


if __name__ == '__main__':
    unittest.main()

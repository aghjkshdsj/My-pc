import importlib.util
import pathlib
import unittest

spec = importlib.util.spec_from_file_location('verify', pathlib.Path(__file__).with_name('verify-config.py'))
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


class ConfigurationTests(unittest.TestCase):
    def test_meson_boolean_and_numeric_definitions(self):
        for enabled in ('#define CONFIG_TCG_THREADED_INTERPRETER\n', '#define CONFIG_TCG_THREADED_INTERPRETER 1\n'):
            verify.verify_configuration(enabled + '/* #undef CONFIG_TCG_INTERPRETER */\n/* #undef CONFIG_HVF */\n')

    def test_disabled_or_missing_interpreter_fails_closed(self):
        for disabled in ('', '/* #undef CONFIG_TCG_THREADED_INTERPRETER */', '#define CONFIG_TCG_THREADED_INTERPRETER 0', '#define CONFIG_TCG_THREADED_INTERPRETER_EXTRA 1'):
            with self.assertRaises(AssertionError):
                verify.verify_configuration(disabled)

    def test_conflicting_backends_fail_closed(self):
        for other in ('CONFIG_HVF', 'CONFIG_TCG_INTERPRETER'):
            for value in ('', ' 1', ' 0'):
                with self.assertRaises(AssertionError):
                    verify.verify_configuration('#define CONFIG_TCG_THREADED_INTERPRETER\n#define ' + other + value + '\n')


if __name__ == '__main__':
    unittest.main()

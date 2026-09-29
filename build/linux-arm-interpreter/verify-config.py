#!/usr/bin/env python3
"""Fail closed if the packaged runtime was not built with the interpreter."""
import argparse
import hashlib
import json
import pathlib
import re

def verify_configuration(config):
    # Meson configuration_data.set(name, True) emits a valueless #define.
    # Numeric set(name, 1) emits "1". Accept those two enabled forms only.
    assert re.search(r'^#define[ \t]+CONFIG_TCG_THREADED_INTERPRETER(?:[ \t]+1)?[ \t]*$', config, re.M), 'TCTI is not enabled'
    assert not re.search(r'^#define[ \t]+CONFIG_TCG_INTERPRETER\b', config, re.M), 'Unexpected classic TCI backend'
    assert not re.search(r'^#define[ \t]+CONFIG_HVF\b', config, re.M), 'Unexpected hypervisor backend'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=pathlib.Path)
    parser.add_argument('output', type=pathlib.Path)
    args = parser.parse_args()
    headers = list(args.source.rglob('config-host.h'))
    assert len(headers) == 1, f'Expected one QEMU configuration, found {len(headers)}'
    config = headers[0].read_text()
    verify_configuration(config)
    region = (args.source / 'tcg/region.c').read_text()
    assert re.search(r'#if defined\(CONFIG_TCG_INTERPRETER\) \|\| defined\(CONFIG_TCG_THREADED_INTERPRETER\)\s+/\* The tcg interpreter does not need execute permission\. \*/\s+prot = PROT_READ \| PROT_WRITE;', region)
    args.output.mkdir(parents=True, exist_ok=True)
    binary = args.output / 'Frameworks/qemu-aarch64-softmmu.framework/qemu-aarch64-softmmu'
    report = {'schema': 1, 'backend': 'tcti', 'hostArchitecture': 'arm64',
              'requiresJIT': False, 'qemuVersion': '10.0.12-utm',
              'binarySHA256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'configSHA256': hashlib.sha256(config.encode()).hexdigest()}
    (args.output / 'runtime-backend.json').write_text(json.dumps(report, indent=2) + '\n')
    (args.output / 'config-host.h').write_text(config)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Inventory completeness and new-project contamination/build-input gate."""
import csv
import hashlib
import json
import pathlib
import plistlib
import xml.etree.ElementTree as ET

root = pathlib.Path(__file__).resolve().parents[1]
summary = json.loads((root / 'evidence/archive-summary.json').read_text(encoding='utf-8'))
rows = list(csv.DictReader((root / 'evidence/archive-files.csv').open(encoding='utf-8', newline='')))
assert len(rows) == len({x['path'] for x in rows}) == summary['files'] == 3672
assert sum(int(x['bytes']) for x in rows) == summary['expanded_bytes'] == 166226171
assert summary['sha256'] == '74644b0d98e7be56f931ec1d5c1be455f52841e216edef7a3597d9e67f1529e6'
for group, count in summary['component_counts'].items():
    assert sum(x['component'] == group for x in rows) == count
    assert group in (root / 'docs/COMPONENTS.md').read_text(encoding='utf-8')
for row in rows:
    assert len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256'])
    assert '..' not in pathlib.PurePosixPath(row['path']).parts
blueprint = root / 'evidence/droiddeck-summary.json'
if blueprint.exists():
    android = json.loads(blueprint.read_text(encoding='utf-8'))
    files = list(csv.DictReader((root / 'evidence/droiddeck-files.csv').open(encoding='utf-8', newline='')))
    assert android['scope'] == 'android-blueprint-archive-inventory-only'
    assert android['sha256'] == 'd55ebf34a488cd15b34eb523e4bca16ae7a96b970e02cfa26d53b1f1fdc1009b'
    assert android['all_file_crc_passed'] is True
    assert len(files) == len({x['path'] for x in files}) == android['files'] == 735
    assert sum(int(x['bytes']) for x in files) == android['expanded_bytes'] == 52717893
    for category, data in android['groups'].items():
        members = [x for x in files if x['group'] == category]
        assert len(members) == data['files']
        assert sum(int(x['bytes']) for x in members) == data['bytes']
    for row in files:
        path = pathlib.PurePosixPath(row['path'])
        assert not path.is_absolute() and '..' not in path.parts
        if row['group'] == 'signing-material-withheld':
            assert row['path'].startswith('withheld-signing-input-') and row['sha256'] == 'withheld'
        else:
            assert len(row['sha256']) == 64 and all(c in '0123456789abcdef' for c in row['sha256'])
    assert not any(android[k] for k in ['scripts_executed', 'source_application_reused',
                                      'signing_content_exported', 'phone_linux_gpu_verified',
                                      'steam_boot_verified', 'game_performance_verified'])
    assert (root / 'docs/DROIDDECK-BLUEPRINT.md').is_file()
    print('BLUEPRINT_GATE_OK: all 735 DroidDeck files accounted for; signing inputs withheld')
project = (root / 'MyPCSteamOS.xcodeproj/project.pbxproj').read_text(encoding='utf-8')
for forbidden in ['Madeira', 'native-ios/', 'LinuxVMCore', '../My-pc', 'steam-native-candidate', 'baseline/']:
    assert forbidden not in project
info = plistlib.loads((root / 'Host/Info.plist').read_bytes())
assert info['CFBundleDisplayName'] == 'My-pc SteamOS Probe'
scheme = ET.parse(root / 'MyPCSteamOS.xcodeproj/xcshareddata/xcschemes/MyPCSteamOSProbe.xcscheme').getroot()
assert scheme.find('LaunchAction').attrib['buildConfiguration'] == 'Release'
assert scheme.find('LaunchAction').attrib['selectedDebuggerIdentifier'] == ''
for name in ['ProbeApp.swift', 'ProbeBridge.mm', 'LinuxGate.mm', 'RecoveryJournal.swift', 'ProbeRecovery.mm']:
    assert 'Host/' + name in project
print('SOURCE_GATE_OK: all 3672 archive files accounted for; fresh project inputs isolated')

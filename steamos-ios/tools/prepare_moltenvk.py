#!/usr/bin/env python3
"""Prepare/package a pinned low-level iOS graphics engine in a new build folder."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tarfile

from verify_ipa import macho_platform

REVISION = '05604465d691118cfd20f53a48ecf1aad9c12f93'
# Exact commits from the reviewed MoltenVK ExternalRevisions tree.
DEPENDENCIES = {
    'cereal': ('USCiLab/cereal', 'a56bad8bbb770ee266e930c95d37fff2a5be7fea'),
    'Vulkan-Headers': ('KhronosGroup/Vulkan-Headers', '6aefb8eb95c8e170d0805fd0f2d02832ec1e099a'),
    'SPIRV-Cross': ('utmapp/SPIRV-Cross', '939b40b33a44443c404c4078823c406e3c94866f'),
    'SPIRV-Tools': ('KhronosGroup/SPIRV-Tools', '262bdab48146c937467f826699a40da0fdfc0f1a'),
    'SPIRV-Tools/external/spirv-headers': ('KhronosGroup/SPIRV-Headers', 'b824a462d4256d720bebb40e78b9eb8f78bbb305'),
    'Vulkan-Tools': ('KhronosGroup/Vulkan-Tools', '013058f74e2356347f8d9317233bc769816c9dfb'),
    'Volk': ('zeux/volk', '59660878571aa99e3c9a366bb1d19fdcd701f0e7'),
}


def git(path, *args, capture=False):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    return subprocess.run(['git', '-C', str(path), *args], check=True, env=env,
                          stdout=subprocess.PIPE if capture else None,
                          text=capture).stdout


def checkout(path, repository, revision):
    assert not path.exists(), f'Refusing to replace existing source: {path}'
    assert re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_-]+', repository)
    assert re.fullmatch(r'[0-9a-f]{40}', revision)
    path.mkdir(parents=True)
    git(path, 'init', '-q')
    git(path, 'remote', 'add', 'origin', f'https://github.com/{repository}.git')
    git(path, 'fetch', '--depth=1', 'origin', revision)
    git(path, 'checkout', '--detach', 'FETCH_HEAD')
    assert git(path, 'rev-parse', 'HEAD', capture=True).strip() == revision


def blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def prepare(output):
    assert not output.exists(), 'Use a new build directory; existing projects are never replaced'
    output.mkdir(parents=True)
    source = output / 'MoltenVK'
    checkout(source, 'utmapp/MoltenVK', REVISION)
    original = (source / 'fetchDependencies').read_bytes()
    assert blob(original) == 'aa03732d15affa1b452d2c03fad40de0c92325eb'
    assert 'Apache License' in (source / 'LICENSE').read_text()
    for name, (repository, revision) in DEPENDENCIES.items():
        revision_name = 'SPIRV-Headers' if name.endswith('/spirv-headers') else name
        assert (source / 'ExternalRevisions' / (revision_name + '_repo_revision')).read_text().strip() == revision
        checkout(source / 'External' / name, repository, revision)
    # Upstream's downloader is replaced with checks of our already pinned trees.
    # Nothing recursively deletes/replaces source directories or follows an online branch.
    derived, count = re.subn(r'^function update_repo\(\) \{\n.*?^\}', '''function update_repo() {
    actual=$(git -C "$1" rev-parse HEAD)
    test "$actual" = "$3" || { echo "Unexpected dependency revision: $1" >&2; exit 1; }
}''', original.decode(), flags=re.MULTILINE | re.DOTALL)
    assert count == 1
    assert derived.count('xcodebuild "$@"') == 2
    derived = derived.replace('xcodebuild "$@"',
        'xcodebuild "$@" CODE_SIGNING_ALLOWED=NO IPHONEOS_DEPLOYMENT_TARGET=26.0 ARCHS=arm64 ONLY_ACTIVE_ARCH=YES')
    (source / 'fetchDependencies-pinned').write_text(derived)
    finish = source / 'Scripts/package_ext_libs_finish.sh'
    finish_source = finish.read_text()
    assert finish_source.count('make --quiet clean') == 1
    finish.write_text(finish_source.replace('make --quiet clean', ': # New source tree needs no macOS clean target'))
    # The upstream iOS dynamic target unnecessarily links the macOS IOKit
    # framework. Do not ship that required macOS install-name in an iOS engine.
    project = source / 'MoltenVK/MoltenVK.xcodeproj/project.pbxproj'
    project_text = project.read_text()
    link = '\t\t\t\tA9F4D9902B8E7D66004AD576 /* IOKit.framework in Frameworks */,\n'
    assert project_text.count(link) == 1
    project.write_text(project_text.replace(link, ''))
    (output / 'ios-framework-link.patch').write_text(git(source, 'diff', '--',
        'MoltenVK/MoltenVK.xcodeproj/project.pbxproj', capture=True))
    receipt = {'kind': 'fresh-ios-moltenvk-engine-preparation', 'revision': REVISION,
               'original_fetch_git_blob': blob(original), 'derived_fetch_sha256': hashlib.sha256(derived.encode()).hexdigest(),
               'dependencies': {name: {'repository': repo, 'commit': rev}
                                for name, (repo, rev) in DEPENDENCIES.items()},
               'changes': ['check pre-fetched exact dependency commits', 'unsigned ARM64 iOS 26 dependency builds',
                           'skip unrelated macOS clean in a fresh tree',
                           'remove IOKit from the iOS dynamic target framework phase'],
               'application_base': 'fresh-steamos-ios', 'phone_tested': False}
    (output / 'source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')


def package(output):
    source = output / 'MoltenVK'
    frameworks = list((source / 'Package/Release/MoltenVK/dynamic').rglob('MoltenVK.framework'))
    assert len(frameworks) == 1, frameworks
    framework = frameworks[0]
    binary = (framework / 'MoltenVK').read_bytes()
    imports = macho_platform(binary, 6)
    assert all(x.startswith('/System/Library/Frameworks/') or x.startswith('/usr/lib/') for x in imports), imports
    assert not any('Hypervisor' in x or 'PrivateFrameworks' in x for x in imports)
    assert not any('IOKit' in x for x in imports), 'Unexpected macOS IOKit dependency in iOS engine'
    nm = subprocess.check_output(['nm', '-gU', str(framework / 'MoltenVK')], text=True)
    for symbol in ['_vkCreateInstance', '_vkCreateDevice', '_vkCreateGraphicsPipelines',
                   '_vkCmdDraw', '_vkGetMemoryHostPointerPropertiesEXT']:
        assert symbol in nm, symbol
    (output / 'engine-exports.txt').write_text(nm)
    frameworks_dir = output / 'Frameworks'; frameworks_dir.mkdir()
    shutil.copytree(framework, frameworks_dir / 'MoltenVK.framework', symlinks=True)
    bundle = output / 'MoltenVK-iOS-Framework.tar.gz'
    with tarfile.open(bundle, 'w:gz') as archive:
        archive.add(frameworks_dir, arcname='Frameworks')
    # Exact tracked source for the engine and every dependency; no object/build/.git trees.
    source_dir = output / 'corresponding-source'; source_dir.mkdir()
    for name, path in [('MoltenVK', source), *[(n.replace('/', '-'), source / 'External' / n) for n in DEPENDENCIES]]:
        git(path, 'archive', '--format=tar', '-o', str((source_dir / (name + '.tar')).resolve()), 'HEAD')
    shutil.copy2(source / 'fetchDependencies-pinned', source_dir)
    shutil.copy2(source / 'Scripts/package_ext_libs_finish.sh', source_dir / 'package_ext_libs_finish.modified.sh')
    shutil.copy2(output / 'source-receipt.json', source_dir)
    shutil.copy2(output / 'ios-framework-link.patch', source_dir)
    shutil.copy2(__file__, source_dir)
    workflow = pathlib.Path(__file__).resolve().parents[2] / '.github/workflows/steamos-ios-moltenvk.yml'
    shutil.copy2(workflow, source_dir)
    with tarfile.open(output / 'MoltenVK-Corresponding-Source.tar.gz', 'w:gz') as archive:
        archive.add(source_dir, arcname='corresponding-source')
    files = {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
             for p in [bundle, output / 'MoltenVK-Corresponding-Source.tar.gz']}
    result = {'kind': 'source-built-arm64-ios-moltenvk-engine', 'revision': REVISION,
              'binary_bytes': len(binary), 'binary_sha256': hashlib.sha256(binary).hexdigest(),
              'physical_ios_macho': True, 'imports': imports, 'files': files,
              'source_commit': os.environ.get('GITHUB_SHA'), 'workflow_run': os.environ.get('GITHUB_RUN_ID'),
              'phone_tested': False, 'guest_transport_verified': False, 'metal_execution_verified': False,
              'steamos_verified': False, 'gameplay_verified': False}
    (output / 'engine-receipt.json').write_text(json.dumps(result, indent=2) + '\n')
    (output / 'SHA256SUMS').write_text(''.join(f"{entry['sha256']}  {name}\n" for name, entry in files.items()))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'package'])
    parser.add_argument('directory', type=pathlib.Path)
    args = parser.parse_args()
    (prepare if args.action == 'prepare' else package)(args.directory.resolve())

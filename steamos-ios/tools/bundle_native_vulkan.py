#!/usr/bin/env python3
"""Stage exact engine, official headers and checked shaders into the fresh app."""
import argparse
import hashlib
import io
import json
import pathlib
import shutil
import tarfile

from bundle_linux_gate import extract_checked
from verify_ipa import macho_platform

FRAMEWORK_SHA = '6f34d5e31466d6fd096ddf48a270228606cd5f249089cef1fe06dbea522d3c68'
SOURCE_SHA = '4547b750ec6e45ba5cccce0342e8af275ee2ed657eab020732b65961ac489e28'
BINARY_SHA = '6554b9549ca42c49a63ddd05f258f8e173c7fbeac246ff5052f377c51473fa9d'
SHADERS = {'vertex.spv': '58a13742238c0651b8eeda455ba8962c12f41d9d627cd90480d3ed38cdf90a5c',
           'fragment.spv': '7c117856eaaa2b8d37c47a569e861713550c7563ebdfc880b2a389667d57e368'}
PROJECT = pathlib.Path(__file__).resolve().parents[1]
STAGE = PROJECT / 'out/native-vulkan'


def digest(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()


def prepare(engine, shaders):
    assert digest(engine / 'MoltenVK-iOS-Framework.tar.gz') == FRAMEWORK_SHA
    assert digest(engine / 'MoltenVK-Corresponding-Source.tar.gz') == SOURCE_SHA
    extract_checked(engine / 'MoltenVK-iOS-Framework.tar.gz', STAGE)
    binary = STAGE / 'Frameworks/MoltenVK.framework/MoltenVK'
    assert digest(binary) == BINARY_SHA
    imports = macho_platform(binary.read_bytes(), 6)
    assert not any('IOKit' in x or 'PrivateFrameworks' in x or 'Hypervisor' in x for x in imports)
    with tarfile.open(engine / 'MoltenVK-Corresponding-Source.tar.gz') as outer:
        data = outer.extractfile('corresponding-source/Vulkan-Headers.tar').read()
    headers = STAGE / 'headers'; headers.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive.getmembers():
            if not member.name.startswith('include/') or not member.isfile(): continue
            path = pathlib.PurePosixPath(member.name).relative_to('include')
            assert not path.is_absolute() and '..' not in path.parts
            destination = headers.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.extractfile(member).read())
    assert (headers / 'vulkan/vulkan.h').is_file()
    payload = STAGE / 'NativeVulkan'; payload.mkdir()
    for name, sha in SHADERS.items():
        assert digest(shaders / name) == sha
        shutil.copy2(shaders / name, payload / name)
    files = {'MoltenVK': {'bytes': binary.stat().st_size, 'sha256': BINARY_SHA}}
    files.update({name: {'bytes': (payload / name).stat().st_size, 'sha256': sha} for name, sha in SHADERS.items()})
    receipt = {'schema': 1, 'scope': 'bundled-native-ios-vulkan-diagnostic',
               'engine_commit': '05604465d691118cfd20f53a48ecf1aad9c12f93', 'engine_run': 37056046870,
               'engine_recipe_commit': '5f9805fded4390780798c25b8a7465db36234fe3',
               'header_commit': '6aefb8eb95c8e170d0805fd0f2d02832ec1e099a', 'shader_run': 37035517982,
               'source_archive_sha256': SOURCE_SHA, 'files': files,
               'phone_tested': False, 'linux_graphics_verified': False, 'gameplay_verified': False}
    (payload / 'payload-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


def bundle(app):
    shutil.copytree(STAGE / 'Frameworks/MoltenVK.framework', app / 'Frameworks/MoltenVK.framework')
    shutil.copytree(STAGE / 'NativeVulkan', app / 'NativeVulkan')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('engine', type=pathlib.Path); prep.add_argument('shaders', type=pathlib.Path)
    pack = sub.add_parser('bundle'); pack.add_argument('app', type=pathlib.Path)
    args = parser.parse_args()
    prepare(args.engine, args.shaders) if args.action == 'prepare' else bundle(args.app)

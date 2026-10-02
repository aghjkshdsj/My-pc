#!/usr/bin/env python3
"""Close the Linux ELF runtime; retain authenticated exact Ubuntu source packages."""
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess


def capture(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def needed(path):
    data = path.read_bytes()
    assert data[:6] == b'\x7fELF\x02\x01' and int.from_bytes(data[18:20], 'little') == 183, path
    return re.findall(r'\(NEEDED\).*?Shared library: \[([^\]]+)\]', capture('readelf', '-d', str(path)))


def package(path):
    candidates = [str(path), str(path.resolve())]
    candidates += [p.removeprefix('/usr') for p in candidates if p.startswith('/usr/lib/')]
    for name in candidates:
        result = subprocess.run(['dpkg-query', '-S', name], text=True, capture_output=True)
        if result.returncode == 0:
            owners = [line.rsplit(': ', 1)[0] for line in result.stdout.splitlines() if ': ' in line]
            assert len(owners) == 1, (path, owners)
            owner = owners[0]
            fields = capture('dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${source:Package}\t${source:Version}', owner).split('\t')
            assert len(fields) == 4 and all(fields), fields
            return dict(zip(['binary', 'version', 'source', 'source_version'], fields))
    raise AssertionError('No exact distribution package owns ' + str(path))


def fetch_sources(packages, output):
    """Use a separate APT source/list directory, preserving host configuration."""
    output.mkdir()
    sourceparts = output / 'apt-sourceparts'
    sourceparts.mkdir()
    config = pathlib.Path('/etc/apt/sources.list.d/ubuntu.sources')
    text = config.read_text(encoding='utf-8')
    assert 'Signed-By:' in text and re.search(r'^Types:\s+deb\s*$', text, re.MULTILINE)
    uris = re.findall(r'^URIs:\s+(.*)$', text, re.MULTILINE)
    assert uris and all(re.fullmatch(r'https?://(?:ports|archive|security)\.ubuntu\.com/[^\s]*', uri)
                        for line in uris for uri in line.split()), uris
    text = re.sub(r'^Types:\s+deb\s*$', 'Types: deb-src', text, flags=re.MULTILINE)
    (sourceparts / 'ubuntu.sources').write_text(text, encoding='utf-8')
    state = output / 'apt-lists'
    state.mkdir()
    (state / 'partial').mkdir()
    options = ['-o', 'Dir::Etc::sourcelist=/dev/null', '-o', 'Dir::Etc::sourceparts=' + str(sourceparts),
               '-o', 'Dir::State::lists=' + str(state)]
    subprocess.run(['sudo', 'apt-get', *options, 'update'], check=True)
    specifications = sorted({row['source'] + '=' + row['source_version'] for row in packages})
    downloads = output / 'packages'
    downloads.mkdir()
    for specification in specifications:
        subprocess.run(['apt-get', *options, 'source', '--download-only', specification],
                       cwd=downloads, check=True)
    dscs = list(downloads.glob('*.dsc'))
    assert len(dscs) == len(specifications), (specifications, dscs)
    # APT authenticates the signed Sources indices. Additionally compare every
    # source file with the exact checksum recorded by its downloaded .dsc.
    for path in dscs:
        text = path.read_text(encoding='utf-8')
        section = re.search(r'^Checksums-Sha256:\n((?: .+\n)+)', text, re.MULTILINE)
        assert section, path
        for line in section[1].splitlines():
            sha, size, name = line.split()
            assert pathlib.PurePosixPath(name).name == name and re.fullmatch('[0-9a-f]{64}', sha)
            archive = downloads / name
            assert archive.stat().st_size == int(size) and digest(archive) == sha, name
    return {'exact_source_specifications': specifications, 'apt_signature_checks_required': True,
            'source_archives': {p.name: {'bytes': p.stat().st_size, 'sha256': digest(p)}
                                for p in sorted(downloads.iterdir()) if p.is_file()}}


def stage(root, source_output):
    """Resolve new Mesa libraries first, then copy only required host ARM64 DSOs."""
    assert os.uname().sysname == 'Linux' and os.uname().machine == 'aarch64'
    directory = root / 'usr/lib'
    queue = [p for p in directory.rglob('*') if p.is_file() and not p.is_symlink()
             and p.read_bytes()[:4] == b'\x7fELF'] + [root / 'vk-gate']
    assert queue and (directory / 'libgallium-26.2.2.so').is_file()
    cache = {}
    for line in capture('ldconfig', '-p').splitlines():
        match = re.match(r'\s*(\S+)\s+\([^)]*AArch64[^)]*\)\s+=>\s+(\S+)', line, re.IGNORECASE)
        if match:
            cache.setdefault(match[1], pathlib.Path(match[2]))
    assert 'libc.so.6' in cache and 'libvulkan.so.1' in cache
    copied, checked = {}, set()
    while queue:
        path = queue.pop()
        if path in checked:
            continue
        checked.add(path)
        for name in needed(path):
            assert pathlib.PurePosixPath(name).name == name
            target = directory / name
            if not target.is_file():
                assert name in cache, (path, name)
                original = cache[name]
                row = package(original)
                shutil.copy2(original.resolve(strict=True), target)
                copyright_path = pathlib.Path('/usr/share/doc') / row['binary'].split(':')[0] / 'copyright'
                assert copyright_path.is_file(), copyright_path
                notice = root / 'usr/share/doc' / row['binary'].split(':')[0] / 'copyright'
                notice.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(copyright_path, notice)
                copied[name] = {**row, 'bytes': target.stat().st_size, 'sha256': digest(target),
                                'copyright_sha256': digest(notice)}
            queue.append(target.resolve(strict=True))
    interpreter = re.findall(r'\[Requesting program interpreter: ([^\]]+)\]',
                             capture('readelf', '-l', str(root / 'vk-gate')))
    assert interpreter == ['/lib/ld-linux-aarch64.so.1'], interpreter
    loader = pathlib.Path(interpreter[0])
    loader_row = package(loader)
    destination = root / interpreter[0].removeprefix('/')
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(loader.resolve(strict=True), destination)
    needed(destination)
    copied[destination.relative_to(root).as_posix()] = {**loader_row, 'bytes': destination.stat().st_size,
                                                       'sha256': digest(destination)}
    # The copied loader must resolve every staged ELF using only the staged DSOs.
    listings = {}
    for path in sorted(checked):
        listing = capture(str(destination), '--inhibit-cache', '--library-path', str(directory), '--list', str(path))
        assert 'not found' not in listing
        for resolved in re.findall(r'=>\s+(/\S+)', listing):
            assert pathlib.Path(resolved).is_relative_to(root), (path, resolved)
        listings[path.relative_to(root).as_posix()] = listing
    source_receipt = fetch_sources(list(copied.values()), source_output)
    return {'runtime_files': copied, 'staged_loader_dependency_checks': listings,
            'distribution_sources': source_receipt, 'runtime_dependency_closure_verified': True}

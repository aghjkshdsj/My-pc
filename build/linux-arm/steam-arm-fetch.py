#!/usr/bin/env python3
"""Fetch Valve's ARM64 Linux Steam packages with manifest SHA-256 verification.

Runs inside the Linux guest. --audit downloads just the native client package,
checks ELF architecture, and writes a report; it does not launch or log in.
No Valve binaries are committed or included in our CI report artifacts.
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import stat
import struct
import tempfile
import urllib.request
import zipfile

CDN = "https://client-update.steamstatic.com/"
MANIFEST = "steam_client_publicbeta_linuxarm64"

def parse_manifest(text):
    if len(text) > 2_000_000:
        raise ValueError("Steam manifest exceeds size limit")
    # Valve KeyValues: quoted strings, braces, whitespace, and // comments.
    token = re.compile(r'\s+|//[^\n]*|"((?:\\.|[^"\\])*)"|([{}])')
    tokens = []
    position = 0
    while position < len(text):
        match = token.match(text, position)
        if not match:
            raise ValueError(f"Invalid manifest token at {position}")
        position = match.end()
        if match.group(1) is not None:
            tokens.append(("string", match.group(1)))
        elif match.group(2):
            tokens.append((match.group(2), match.group(2)))
    index = 0
    def object(nested=False, depth=0):
        nonlocal index
        if depth > 12:
            raise ValueError("Manifest nesting exceeds limit")
        result = {}
        while index < len(tokens):
            kind, key = tokens[index]
            index += 1
            if kind == "}" and nested:
                return result
            if kind != "string" or key in result or index == len(tokens):
                raise ValueError("Invalid or duplicate manifest key")
            kind, value = tokens[index]
            index += 1
            if kind == "{":
                value = object(True, depth + 1)
            elif kind != "string":
                raise ValueError("Invalid manifest value")
            result[key] = value
        if nested:
            raise ValueError("Unclosed manifest object")
        return result
    result = object()
    client = result.get("linuxarm64")
    if not isinstance(client, dict) or "version" not in client:
        raise ValueError("Valve did not return a Linux ARM64 manifest")
    packages = []
    for name, value in client.items():
        if not isinstance(value, dict):
            continue
        filename = value.get("file", "")
        digest = value.get("sha2", "").lower()
        size = int(value.get("size", "0"))
        if not re.fullmatch(r"[a-zA-Z0-9_]+\.zip\.[a-fA-F0-9]{40}", filename) or not re.fullmatch(r"[a-f0-9]{64}", digest) or not 0 < size < 2_147_483_648:
            raise ValueError(f"Invalid Valve package metadata: {name}")
        packages.append({"name": name, "file": filename, "sha256": digest, "size": size})
    if not packages or len(packages) > 100 or sum(p["size"] for p in packages) > 4_294_967_296:
        raise ValueError("Incomplete or oversized Valve package set")
    if not any(p["file"].startswith("bins_linuxarm64_linuxarm64.zip.") for p in packages):
        raise ValueError("Native ARM64 client package missing")
    return client["version"], packages

def fetch(url, output, limit, expected_hash=None, expected_size=None):
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url, headers={"User-Agent": "My-pc ARM Linux bootstrap"})
    with urllib.request.urlopen(request, timeout=90) as response, output.open("wb") as stream:
        if not response.url.startswith("https://"):
            raise ValueError("Steam download redirected away from HTTPS")
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > limit:
                raise ValueError("Steam download exceeds declared size")
            digest.update(chunk)
            stream.write(chunk)
    if expected_size is not None and size != expected_size:
        raise ValueError("Steam download size mismatch")
    if expected_hash and digest.hexdigest() != expected_hash:
        raise ValueError("Steam download SHA-256 mismatch")

def extract(archive, destination):
    with zipfile.ZipFile(archive) as package:
        files = package.infolist()
        if len(files) > 100000 or sum(info.file_size for info in files) > 8 * 1024**3:
            raise ValueError("Steam ZIP exceeds extraction limits")
        for info in files:
            name = pathlib.PurePosixPath(info.filename)
            if name.is_absolute() or not name.parts or any(part in ("..", ".") for part in name.parts) or "\\" in info.filename or ":" in info.filename:
                raise ValueError("Unsafe path in Steam ZIP")
            if name.parts[0].lower() in ("steamapps", "userdata", "config"):
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise ValueError("Unexpected symbolic link in Steam ZIP")
            target = destination.joinpath(*name.parts)
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError("Steam ZIP escapes staging directory")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with package.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
            target.chmod(0o755 if mode & 0o111 else 0o644)

def verify_arm64(path):
    with path.open("rb") as binary:
        header = binary.read(64)
    if len(header) != 64 or header[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", header, 18)[0] != 183:
        raise ValueError(f"Not an AArch64 Linux ELF executable: {path}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=pathlib.Path, default=pathlib.Path.home() / ".local/share/Steam")
    parser.add_argument("--audit", action="store_true")
    args = parser.parse_args()
    destination = args.destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".my-pc-steam-", dir=destination.parent) as temporary:
        temporary = pathlib.Path(temporary)
        manifest = temporary / "manifest.vdf"
        fetch(CDN + MANIFEST, manifest, 2_000_000)
        version, packages = parse_manifest(manifest.read_text())
        if args.audit:
            packages = [p for p in packages if p["file"].startswith("bins_linuxarm64_linuxarm64.zip.")]
        staged = temporary / "staged"
        staged.mkdir()
        for package in packages:
            print(f"Verifying {package['name']} ({package['size']} bytes)", flush=True)
            archive = temporary / package["file"]
            fetch(CDN + package["file"], archive, package["size"], package["sha256"], package["size"])
            extract(archive, staged)
        steam = staged / "steamrtarm64/steam"
        verify_arm64(steam)
        report = {"manifest": CDN + MANIFEST, "version": version, "architecture": "ELF64 AArch64 (EM_AARCH64=183)", "packages": packages, "steam_sha256": hashlib.sha256(steam.read_bytes()).hexdigest(), "launched": False}
        if not args.audit:
            # Preserve account state and games. Only commit verified package files.
            for source in staged.rglob("*"):
                relative = source.relative_to(staged)
                target = destination / relative
                if target.is_symlink() or not target.resolve().is_relative_to(destination):
                    raise ValueError("Unsafe existing Steam installation path")
                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, target)
            (destination / "package").mkdir(exist_ok=True)
            (destination / "package/beta").write_text("publicbeta\n")
            (destination / "steamrtarm64/steam").chmod(0o755)
        (destination / "arm64-verification.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()

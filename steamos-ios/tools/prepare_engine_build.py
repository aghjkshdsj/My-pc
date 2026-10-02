#!/usr/bin/env python3
"""Prepare the upstream iOS QEMU engine only, never the UTM application.

Downloads a source-pinned upstream build recipe and derives a narrow CPU-only
recipe with assertions. The upstream ISC notice remains in the derived file.
No previous project is an input. No private hypervisor is built or linked.
"""
import argparse
import hashlib
import json
import pathlib
import re
import urllib.request

UTM = '7eadb056ae0f91d979059544d0ddcd2d5a40be92'
FILES = {
    'scripts/build_dependencies.sh': '4ef513ae4d896af91fc8965865db6b475e993233',
    'scripts/fixup.sh': '354ac3286015eff380d2867c9863f7709ea02921',
    'patches/gettext-0.22.5.patch': '153187928acf41c68067348fce61d16e65ca3b5e',
    'patches/pixman-0.38.0.patch': '2ff4fcc5d570f344cc5836750eabffcfc7083416',
    'patches/qemu-10.0.12-utm.patch': 'fadb8041f6eba76edf78226586eedb54fdb99c75',
}

def get(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'MyPCSteamOS-source-bringup'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()

def git_blob(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def replace_function(text, name, body):
    pattern = rf'^{re.escape(name)}\s*\(\) \{{\n.*?^\}}'
    result, count = re.subn(pattern, lambda _: name + '() {\n' + body + '\n}', text,
                          flags=re.MULTILINE | re.DOTALL)
    assert count == 1, (name, count)
    return result

def prepare(output):
    output.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for name, blob in FILES.items():
        data = get(f'https://raw.githubusercontent.com/utmapp/UTM/{UTM}/{name}')
        assert git_blob(data) == blob, name
        path = output / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        receipts[name] = {'git_blob': blob, 'sha256': hashlib.sha256(data).hexdigest()}
    source_data = get(f'https://raw.githubusercontent.com/utmapp/UTM/{UTM}/patches/sources')
    sources = source_data.decode()
    # Explicit named dependency list, copied from the pinned upstream manifest.
    wanted = ['PKG_CONFIG_SRC', 'FFI_SRC', 'ICONV_SRC', 'GETTEXT_SRC', 'GLIB_SRC',
              'PIXMAN_SRC', 'QEMU_SRC', 'LIBUCONTEXT_REPO', 'LIBUCONTEXT_COMMIT']
    lines = []
    for name in wanted:
        matches = re.findall(rf'^{name}="([^"]+)"$', sources, re.MULTILINE)
        assert len(matches) == 1, name
        value = matches[0].replace('http://ftp.gnu.org/', 'https://ftp.gnu.org/')
        lines.append(f'{name}="{value}"')
    (output / 'patches/sources').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    source = (output / 'scripts/build_dependencies.sh').read_text()
    assert source.count('IOS_SDKMINVER="15.0"') == 1
    source = source.replace('IOS_SDKMINVER="15.0"', 'IOS_SDKMINVER="26.0"')
    source = replace_function(source, 'check_env', '''    for tool in brew python3 meson cmake msgfmt glib-mkenums glib-compile-resources xcrun otool install_name_tool; do
        command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
    done''')
    source = replace_function(source, 'download_all', '''    mkdir -p "$BUILD_DIR"
    for url in "$PKG_CONFIG_SRC" "$FFI_SRC" "$ICONV_SRC" "$GETTEXT_SRC" "$GLIB_SRC" "$PIXMAN_SRC" "$QEMU_SRC"; do
        download "$url"
    done
    clone "$LIBUCONTEXT_REPO" "$LIBUCONTEXT_COMMIT"''')
    source = replace_function(source, 'copy_private_headers', '    : # CPU gate uses no copied private framework headers.')
    source = replace_function(source, 'build_qemu_dependencies', '''    build "$FFI_SRC"
    build "$ICONV_SRC"
    gl_cv_onwards_func_strchrnul=future build "$GETTEXT_SRC" --disable-java
    meson_build "$GLIB_SRC" -Dtests=false -Ddtrace=disabled -Dintrospection=disabled
    build "$PIXMAN_SRC"
    meson_build "$LIBUCONTEXT_REPO" -Ddefault_library=static -Dfreestanding=true''')
    before_unpack = '    if [ -d "$DIR" ]; then\n        echo "${GREEN}Deleting existing build directory ${DIR}...${NC}"'
    assert source.count(before_unpack) == 1
    source = source.replace(before_unpack, '''    if [ "$URL" = "$QEMU_SRC" ]; then
        echo "7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a  $TARGET" | shasum -a 256 -c -
    fi
''' + before_unpack)
    source = source.replace('HVF_FLAGS="--enable-hvf-private"', 'HVF_FLAGS="--disable-hvf"')
    call = 'build $QEMU_DIR --cross-prefix="" $QEMU_PLATFORM_BUILD_FLAGS $QEMU_DEBUG_FLAGS'
    assert source.count(call) == 1
    source = source.replace(call, call + ''' --target-list=aarch64-softmmu --without-default-features --enable-tcg --disable-docs --disable-tools --disable-guest-agent --disable-plugins --disable-spice --disable-opengl --disable-virglrenderer --disable-vnc --disable-curl --disable-slirp''')
    tail = 'build_spice_client\nbuild_vulkan_drivers\nbuild_d3d_drivers\nfixup_all\nremove_shared_gst_plugins # another hack...'
    assert source.count(tail) == 1
    source = source.replace(tail, 'fixup_all')
    # All transforms fail closed on an upstream layout change.
    assert '--enable-hvf-private' not in source
    assert 'build_hypervisor\n' not in source[source.index('# parse args'):]
    derived = output / 'scripts/build_cpu_gate.sh'
    derived.write_text(source, encoding='utf-8')
    (output / 'scripts/fixup.sh').chmod(0o755)
    (output / 'recipe-receipt.json').write_text(json.dumps({
        'schema': 1, 'utm_revision': UTM, 'scope': 'upstream-engine-build-recipe-only',
        'application_base': 'fresh-steamos-ios', 'hardware_virtualization': False,
        'original_sources': receipts, 'derived_sha256': hashlib.sha256(source.encode()).hexdigest(),
        'qemu_archive_sha256': '7c9605290b34152debb842e965a55d2e4fbba4793e536ab677b4027e5dc0ba1a',
        'gpu_support': False, 'phone_tested': False,
    }, indent=2) + '\n')
    print(derived)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=pathlib.Path)
    prepare(parser.parse_args().output)

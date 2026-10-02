#!/bin/bash
set -euo pipefail
driver="$(cd "$(dirname "$0")" && pwd)"
runtime="$driver/runtime"
test -f "$runtime/.mypc-native-overlay.json"
cd "$runtime"
component=${1:?Specify fex, wine, dxmt or dock}
mkdir -p "$driver/out"

case "$component" in
  fex)
    python3 "$driver/fex-build-fixes.py"
    cmake -S FEX -B FEX/build-ios -G Ninja \
      -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_SYSTEM_PROCESSOR=arm64 \
      -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=26.0 \
      -DCMAKE_OSX_SYSROOT="$(xcrun --sdk iphoneos --show-sdk-path)" \
      -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
      -DTUNE_CPU=generic -DBUILD_TESTING=OFF -DBUILD_FEX_LINUX_TESTS=OFF \
      -DBUILD_THUNKS=OFF -DBUILD_FEXCONFIG=OFF -DBUILD_STEAM_SUPPORT=OFF \
      -DENABLE_ZYDIS=OFF -DENABLE_LTO=OFF -DENABLE_CCACHE=OFF \
      -DENABLE_FEX_ALLOCATOR=OFF -DENABLE_JEMALLOC_GLIBC_ALLOC=OFF \
      -DENABLE_ASSERTIONS=OFF
    cmake --build FEX/build-ios --target FEXCore FEXCore_Base JemallocLibs --parallel 3
    xcrun lipo FEX/build-ios/FEXCore/Source/libFEXCore.a -verify_arch arm64
    tar -cf "$driver/out/native-fex.tar" FEX/build-ios
    ;;
  wine)
    python3 "$driver/wine-build-fixes.py"
    brew list --versions bison >/dev/null 2>&1 || brew install bison
    brew list --versions llvm >/dev/null 2>&1 || brew install llvm
    export PATH="$(brew --prefix bison)/bin:$(brew --prefix llvm)/bin:$PATH"
    bash build/gnutls-ios/build.sh
    bash build/ffmpeg/build.sh
    mkdir -p wine/build-macos
    (
      cd wine/build-macos
      ../configure --enable-archs=none --disable-tests --disable-win16 --without-x --without-gnutls
      make -j3 tools/widl/widl
      python3 - <<'PY'
from pathlib import Path
import re, subprocess
headers = sorted(set(re.findall(r'^(include/[^\s:]+\.h)(?:\s[^:\n]*)?:', Path('Makefile').read_text(), re.M)))
assert headers, 'No generated Wine header targets'
subprocess.run(['make', '-j3', *headers], check=True)
PY
    )
    cat >> wine/build-macos/include/config.h <<'EOF'
#undef SONAME_LIBGNUTLS
#define SONAME_LIBGNUTLS "libgnutls.a"
#undef HAVE_GNUTLS_CIPHER_INIT
#define HAVE_GNUTLS_CIPHER_INIT 1
#undef HAVE_SYS_PTRACE_H
#undef HAVE_SYS_USER_H
#undef HAVE_NETINET_TCP_FSM_H
EOF
    if [ ! -d research/freetype/.git ]; then
      git clone --depth 1 --branch VER-2-13-3 https://github.com/freetype/freetype.git research/freetype
    fi
    bash build/freetype-ios/build.sh
    bash build/wineserver/build.sh
    bash build/ntdll-unix/build.sh
    bash build/win32u-unix/build.sh
    for name in gmp nettle hogweed gnutls; do cp "toolchains/gnutls-ios/lib/lib$name.a" app/Madeira/; done
    for name in wineserver ntdll_unix win32u_unix gmp nettle hogweed gnutls avformat avcodec swresample avutil; do
      test -s "app/Madeira/lib$name.a"
      xcrun lipo "app/Madeira/lib$name.a" -verify_arch arm64
    done
    tar -cf "$driver/out/native-wine.tar" app/Madeira/lib*.a
    ;;
  dxmt)
    python3 "$driver/dxmt-build-fixes.py"
    # LLVM's locked headers and iOS libraries may be restored by CI.
    if [ ! -s toolchains/llvm-ios-build/lib/libLLVMPasses.a ]; then
      bash "$driver/build-llvm.sh"
    fi
    xcodebuild -downloadComponent MetalToolchain
    mkdir -p build/dxmt-ios/shader-headers
    for shader in air_msad air_samplepos air_tessellation; do
      xcrun -sdk macosx metal -std=metal3.1 --target=air64-apple-macos14.0 \
        -c "dxmt/src/airconv/shaders/$shader.metal" -o "build/dxmt-ios/shader-headers/$shader.air"
      xxd -n "$shader" -i "build/dxmt-ios/shader-headers/$shader.air" "build/dxmt-ios/shader-headers/$shader.h"
    done
    bash build/dxmt-ios/build.sh
    xcrun --sdk iphoneos libtool -static -o app/Madeira/libdxmt_combined.a \
      build/dxmt-ios/obj/*.o toolchains/llvm-ios-build/lib/*.a
    xcrun lipo app/Madeira/libdxmt_combined.a -verify_arch arm64
    tar -cf "$driver/out/native-dxmt.tar" app/Madeira/libdxmt_combined.a
    ;;
  dock)
    python3 - "$driver/source-lock.json" <<'PY'
from pathlib import Path
import json, hashlib, urllib.request, sys, tarfile
lock = json.loads(Path(sys.argv[1]).read_text())['llvm_mingw']
target = Path('toolchains'); target.mkdir(exist_ok=True)
archive = target / 'llvm-mingw.tar.xz'
if not archive.exists():
    with urllib.request.urlopen(lock['url'], timeout=120) as response, archive.open('wb') as output:
        import shutil
        shutil.copyfileobj(response, output)
if hashlib.sha256(archive.read_bytes()).hexdigest() != lock['sha256']:
    raise SystemExit('llvm-mingw SHA-256 mismatch')
with tarfile.open(archive) as source:
    source.extractall(target, filter='data')
PY
    bash build/madeira-dock/build.sh --check
    tar -cf "$driver/out/native-dock.tar" app/Madeira/arm64ec-windows/dockhost.exe app/Madeira/arm64ec-windows/dock-notices.txt
    ;;
  *) echo "Unknown component: $component" >&2; exit 2 ;;
esac

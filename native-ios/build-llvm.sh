#!/bin/bash
set -euo pipefail
mkdir -p toolchains
if [ ! -d toolchains/llvm-project/.git ]; then
    git clone --depth 1 --branch llvmorg-15.0.7 https://github.com/llvm/llvm-project.git toolchains/llvm-project
fi
test "$(git -C toolchains/llvm-project rev-parse HEAD)" = 8dfdcc7b7bf66834a761bd8de445840ef68e4d1a
python3 - <<'PY'
from pathlib import Path
path = Path("toolchains/llvm-project/llvm/cmake/modules/AddLLVM.cmake")
text = path.read_text()
text = text.replace('MATCHES "Darwin"', 'MATCHES "Darwin|iOS"')
path.write_text(text)
PY
common=(
    -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
    -DLLVM_TARGETS_TO_BUILD= -DLLVM_ENABLE_PROJECTS=
    -DLLVM_INCLUDE_TESTS=OFF -DLLVM_INCLUDE_EXAMPLES=OFF
    -DLLVM_INCLUDE_BENCHMARKS=OFF -DLLVM_ENABLE_BINDINGS=OFF
    -DLLVM_ENABLE_ZLIB=OFF -DLLVM_ENABLE_ZSTD=OFF -DLLVM_ENABLE_TERMINFO=OFF
    -DLLVM_ENABLE_LIBXML2=OFF -DLLVM_ENABLE_LIBEDIT=OFF
)
cmake -S toolchains/llvm-project/llvm -B toolchains/llvm-host-build "${common[@]}"
cmake --build toolchains/llvm-host-build --target llvm-tblgen --parallel 3
cmake -S toolchains/llvm-project/llvm -B toolchains/llvm-ios-build "${common[@]}" \
    -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_SYSTEM_PROCESSOR=arm64 \
    -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 \
    -DCMAKE_OSX_SYSROOT="$(xcrun --sdk iphoneos --show-sdk-path)" \
    -DLLVM_TABLEGEN="$PWD/toolchains/llvm-host-build/bin/llvm-tblgen" \
    -DLLVM_DEFAULT_TARGET_TRIPLE=arm64-apple-ios17.0 \
    -DLLVM_HOST_TRIPLE=arm64-apple-ios17.0 \
    -DLLVM_BUILD_TOOLS=OFF -DLLVM_INCLUDE_TOOLS=OFF -DLLVM_BUILD_UTILS=OFF
cmake --build toolchains/llvm-ios-build --target LLVMPasses LLVMBitWriter --parallel 3
test -s toolchains/llvm-ios-build/lib/libLLVMPasses.a


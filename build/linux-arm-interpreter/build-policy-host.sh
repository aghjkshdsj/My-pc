#!/bin/bash
set -euo pipefail
output="$(mkdir -p "$1" && cd "$1" && pwd)"
root="$(cd "$(dirname "$0")/../.." && pwd)"
guard="$output/libmypc-nojit-policy.dylib"
clang -std=c11 -Wall -Wextra -Werror -dynamiclib \
    "$root/build/linux-arm-interpreter/deny-jit-policy.c" \
    -install_name @rpath/libmypc-nojit-policy.dylib -o "$guard"
codesign --force --sign - "$guard"
common=(-std=c11 -Wall -Wextra -Werror -L"$output" -lmypc-nojit-policy -Wl,-rpath,@executable_path)
clang "${common[@]}" "$root/build/linux-arm-interpreter/deny-jit.c" -o "$output/deny-jit"
clang "${common[@]}" -DMYPC_POLICY_PROBE -dynamiclib \
    "$root/build/linux-arm-interpreter/deny-jit.c" -o "$output/policy-probe.dylib"
codesign --force --sign - "$output/policy-probe.dylib"
clang "${common[@]}" -Wno-unused-parameter \
    "$root/build/linux-arm/host-launcher.c" "$root/app/Madeira/LinuxVMBridge.c" \
    -Wl,-rpath,@executable_path/Frameworks -o "$output/host-launcher"
for binary in deny-jit host-launcher; do
    codesign --force --sign - --options runtime \
        --entitlements "$root/build/linux-arm-interpreter/host.entitlements" "$output/$binary"
    codesign --verify --strict "$output/$binary"
done
"$output/deny-jit" "$output/policy-probe.dylib"

#!/bin/bash
set -euo pipefail
driver="$(cd "$(dirname "$0")" && pwd)"
runtime="$driver/runtime"
source_url=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"]["repository"])' "$driver/source-lock.json")
source_commit=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["source"]["commit"])' "$driver/source-lock.json")
if [ ! -d "$runtime/.git" ]; then
    mkdir -p "$runtime"
    git -C "$runtime" init
    git -C "$runtime" remote add origin "$source_url"
    git -C "$runtime" fetch --depth 1 origin "$source_commit"
    git -C "$runtime" checkout --detach FETCH_HEAD
fi
test "$(git -C "$runtime" rev-parse HEAD)" = "$source_commit"
test "$(git -C "$runtime" remote get-url origin)" = "$source_url"
git -C "$runtime" submodule update --init --recursive --depth 1
python3 "$driver/prepare.py" "$runtime"
python3 "$driver/app-overlay.py" "$runtime"

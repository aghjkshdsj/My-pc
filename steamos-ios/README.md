# My-pc SteamOS iOS — fresh bring-up

This source directory and `MyPCSteamOS.xcodeproj` are new. The project links no
Madeira, previous VM app, Wine, FEX or previous native-preview code. Existing
projects, disks, games and account data remain preserved.

The requested product remains an actual SteamOS ARM environment running Valve's
Linux ARM Steam and FEX games. It is **unfinished**. The first separate IPA is
`My-pc SteamOS Probe` (`com.aghjkshdsj.mypc.steamos.probe`, build 4000001).
It tests host Metal computation/readback, a small temporary storage file and a
fixed ARM64 JIT stub after StikDebug. None is a Linux boot or gameplay test.

The owner confirmed iPhone 15 Pro Max, iOS 27.0.1, iLoader and StikDebug on
2026-10-02. The probe records the actual OS build, page size, code-signing state,
Metal device, memory, thermal state and Low Power Mode. Controller enumeration
is recorded but is not reported as a controller test.

Read [architecture and gates](docs/ARCHITECTURE.md),
[component coverage](docs/COMPONENTS.md), [performance measurements](docs/PERFORMANCE.md)
and [upstream provenance](docs/PROVENANCE.md).

## Device step

Install the probe alongside the older apps using iLoader. Run **Metal and storage
probes**, enable StikDebug for **My-pc SteamOS Probe**, then run **ARM64 JIT check**.
Use **Share device report** to return the JSON. If JIT execution terminates the
app, retain the first report and report the failure; do not call it a success.
No account credentials or Steam tokens are collected. Reports remain in the
new app's Documents directory and are never automatically uploaded.

## Build

On a Mac with Xcode's iOS SDK:

```sh
python3 steamos-ios/tools/generate_project.py
xcodebuild -project steamos-ios/MyPCSteamOS.xcodeproj -scheme MyPCSteamOSProbe \
  -configuration Release -sdk iphoneos -destination generic/platform=iOS \
  -derivedDataPath steamos-ios/out/xcode CODE_SIGNING_ALLOWED=NO \
  MPC_SOURCE_COMMIT="$(git rev-parse HEAD)" build
```

CI builds and verifies the exact ARM64 iOS IPA and publishes only a clearly
labelled host probe prerelease, with checksum and corresponding fresh source.
Device signing is supplied by iLoader. JIT must be verified after re-signing.

The private local archive audit hashes and scans every ZIP file without
extracting or running any attached script. `evidence/archive-summary.json` and
`evidence/archive-files.csv` contain distributable inventory receipts.

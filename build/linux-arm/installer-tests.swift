import Foundation
import CryptoKit
import zlib

func check(_ condition: @autoclosure () -> Bool, _ message: String) {
    if !condition() { fatalError(message) }
}
func rejects(_ body: () throws -> Void) {
    do { try body(); fatalError("Expected rejection") } catch { }
}
let fm = FileManager.default
let root = fm.temporaryDirectory.resolvingSymlinksInPath().appendingPathComponent(UUID().uuidString)
let source = root.appendingPathComponent("source")
let destination = root.appendingPathComponent("installed")
try fm.createDirectory(at: source, withIntermediateDirectories: true)
defer { try? fm.removeItem(at: root) }
var kernel = Data(count: 64)
kernel.replaceSubrange(56..<60, with: [0x41, 0x52, 0x4d, 0x64])
let initrd = Data([1, 2, 3, 4])
var disk = Data(count: 4_194_305)
disk.replaceSubrange(1080..<1082, with: [0x53, 0xef])
disk[disk.count - 1] = 42
try kernel.write(to: source.appendingPathComponent("Image"))
try initrd.write(to: source.appendingPathComponent("initrd.img"))
let archive = source.appendingPathComponent("rootfs.raw.gz")
let compressed = gzopen(archive.path, "wb")!
let count = disk.withUnsafeBytes { gzwrite(compressed, $0.baseAddress!, UInt32($0.count)) }
check(count == disk.count, "Could not create gzip fixture")
check(gzclose(compressed) == Z_OK, "Could not close gzip fixture")
var manifest = LinuxRuntimeInstaller.Manifest(schema: 1, architecture: "aarch64", files:
    [("Image", kernel, false), ("initrd.img", initrd, false), ("rootfs.raw", disk, true)].map { name, data, gzip in
        LinuxRuntimeInstaller.Asset(name: name, bytes: Int64(data.count), sha256: StoreFiles.hex(SHA256.hash(data: data)), gzip: gzip)
    })
func saveManifest() throws {
    try JSONEncoder().encode(manifest).write(to: source.appendingPathComponent("manifest.json"))
}
try saveManifest()
try LinuxRuntimeInstaller.install(from: source, to: destination) { _ in }
let actual = try Data(contentsOf: destination.appendingPathComponent("rootfs.raw"))
check(actual == disk, "Streaming/sparse extraction changed the disk")
rejects { try LinuxRuntimeInstaller.install(from: source, to: destination) { _ in } }
check(try! Data(contentsOf: destination.appendingPathComponent("rootfs.raw")) == disk, "Retry must preserve installed disk")
let bad = root.appendingPathComponent("bad")
manifest.files[2].sha256 = String(repeating: "0", count: 64)
try saveManifest()
rejects { try LinuxRuntimeInstaller.install(from: source, to: bad) { _ in } }
check(!fm.fileExists(atPath: bad.path), "Checksum failure committed a disk")
manifest.files[2].sha256 = StoreFiles.hex(SHA256.hash(data: disk))
try saveManifest()
let handle = try FileHandle(forWritingTo: archive)
try handle.truncate(atOffset: 24)
try handle.close()
rejects { try LinuxRuntimeInstaller.install(from: source, to: bad) { _ in } }
check(!fm.fileExists(atPath: bad.path), "Truncated gzip committed a disk")
let remaining = try fm.contentsOfDirectory(atPath: root.path)
check(!remaining.contains(where: { $0.hasPrefix("LinuxARM-staging-") }), "Failed install leaked staging files")
print("PASS: streaming gzip, sparse disk integrity, atomic install, checksums, truncated archive, preservation of existing data")

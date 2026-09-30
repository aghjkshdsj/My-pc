import Foundation
import CryptoKit
import zlib

/// Stream the bundled runtime to an atomic staging directory. The large disk is
/// never held in memory, and an existing Linux installation is never replaced.
enum LinuxRuntimeInstaller {
    struct Manifest: Codable {
        var schema: Int
        var architecture: String
        var files: [Asset]
    }
    struct Asset: Codable {
        var name: String
        var bytes: Int64
        var sha256: String
        var gzip: Bool
    }

    static func install(from source: URL, to destination: URL, progress: @Sendable (Double) -> Void) throws {
        let fm = FileManager.default
        guard !fm.fileExists(atPath: destination.path) else { throw LinuxVMError.invalid("A Linux disk already exists. Your installation will not be overwritten.") }
        let manifestURL = source.appendingPathComponent("manifest.json")
        guard (try manifestURL.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0) < 16_384 else {
            throw LinuxVMError.invalid("Invalid Linux runtime manifest.")
        }
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: manifestURL))
        let limits: [String: Int64] = ["Image": 134_217_728, "initrd.img": 268_435_456, "rootfs.raw": 17_179_869_184]
        guard manifest.schema == 1, manifest.architecture == "aarch64", manifest.files.count == 3,
              Set(manifest.files.map(\.name)) == Set(limits.keys), manifest.files.allSatisfy({ asset in
                  asset.bytes > 0 && asset.bytes <= (limits[asset.name] ?? 0) && asset.sha256.count == 64 &&
                  asset.sha256.allSatisfy { "0123456789abcdef".contains($0) }
              }) else { throw LinuxVMError.invalid("Unsupported Linux runtime manifest.") }
        let total = manifest.files.reduce(Int64(0)) { $0 + $1.bytes }
        let parent = destination.deletingLastPathComponent()
        try StoreFiles.requireSpace(total + 268_435_456, at: parent)
        let stage = parent.appendingPathComponent("LinuxARM-staging-\(UUID().uuidString)")
        try fm.createDirectory(at: stage, withIntermediateDirectories: true)
        defer { try? fm.removeItem(at: stage) }
        var completed: Int64 = 0
        for asset in manifest.files {
            let input = source.appendingPathComponent(asset.name + (asset.gzip ? ".gz" : ""))
            let values = try input.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
            guard values.isRegularFile == true, values.isSymbolicLink != true else {
                throw LinuxVMError.invalid("Invalid runtime asset: \(asset.name)")
            }
            let outputURL = stage.appendingPathComponent(asset.name)
            guard fm.createFile(atPath: outputURL.path, contents: nil) else { throw LinuxVMError.invalid("Cannot create Linux disk.") }
            let output = try FileHandle(forWritingTo: outputURL)
            defer { try? output.close() }
            var digest = SHA256()
            var written: Int64 = 0
            let zeros = Data(count: 1_048_576)
            func write(_ data: Data) throws {
                try Task.checkCancellation()
                written += Int64(data.count)
                guard written <= asset.bytes else { throw LinuxVMError.invalid("Linux runtime expands beyond its declared size.") }
                digest.update(data: data)
                // Preserve empty disk regions as sparse holes on APFS.
                if data == zeros { try output.seek(toOffset: UInt64(written)) }
                else { try output.write(contentsOf: data) }
                if written % 33_554_432 == 0 { progress(Double(completed + written) / Double(total)) }
            }
            if asset.gzip {
                guard let compressed = gzopen(input.path, "rb") else { throw LinuxVMError.invalid("Cannot open compressed Linux runtime.") }
                defer { gzclose(compressed) }
                var buffer = [UInt8](repeating: 0, count: 1_048_576)
                while true {
                    let count = buffer.withUnsafeMutableBytes { gzread(compressed, $0.baseAddress!, UInt32($0.count)) }
                    guard count >= 0 else { throw LinuxVMError.invalid("Damaged compressed Linux runtime.") }
                    if count == 0 {
                        var code: Int32 = 0
                        _ = gzerror(compressed, &code)
                        guard code == Z_OK || code == Z_STREAM_END else { throw LinuxVMError.invalid("Truncated compressed Linux runtime.") }
                        break
                    }
                    try write(Data(buffer.prefix(Int(count))))
                }
            } else {
                let handle = try FileHandle(forReadingFrom: input)
                defer { try? handle.close() }
                while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty { try write(data) }
            }
            guard written == asset.bytes, StoreFiles.hex(digest.finalize()) == asset.sha256 else {
                throw LinuxVMError.invalid("Linux runtime size or checksum mismatch: \(asset.name)")
            }
            try output.truncate(atOffset: UInt64(written))
            try output.synchronize()
            try output.close()
            completed += written
            progress(Double(completed) / Double(total))
        }
        _ = try LinuxVMConfiguration(directory: stage, log: parent.appendingPathComponent("linux.log"),
            control: URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("linux-qmp")).arguments()
        try fm.moveItem(at: stage, to: destination)
    }
}

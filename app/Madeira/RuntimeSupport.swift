import Foundation
import CryptoKit

enum RuntimeSupport {
    struct Manifest: Decodable {
        let version: String
        let major: UInt32
        let minor: UInt32
        let build: UInt32
        let revision: UInt32
        let files: [String: String]
    }

    static func restoreRegistryIfNeeded() throws {
        let prefix = GameLibrary.documents.appendingPathComponent("wine", isDirectory: true)
        let registry = prefix.appendingPathComponent("system.reg")
        let backup = prefix.appendingPathComponent("somethingpc-arm64-registry-backup.json")
        let manager = FileManager.default
        if manager.fileExists(atPath: backup.path) {
            var text = try String(contentsOf: registry, encoding: .utf8)
            let data = try Data(contentsOf: backup)
            text = try RuntimeRegistry.restore(in: text, backup: data)
            try text.write(to: registry, atomically: true, encoding: .utf8)
            try manager.removeItem(at: backup)
        }
    }

    static func prepare(enabled: Bool) throws {
        let prefix = GameLibrary.documents.appendingPathComponent("wine", isDirectory: true)
        madeira_seed_prefix_if_needed(prefix.path)
        try restoreRegistryIfNeeded()
        let registry = prefix.appendingPathComponent("system.reg")
        let backup = prefix.appendingPathComponent("somethingpc-arm64-registry-backup.json")
        let text = try String(contentsOf: registry, encoding: .utf8)
        setenv("SOMETHINGPC_ARM64_VC", enabled ? "1" : "0", 1)
        guard enabled else { return }
        guard let directory = Bundle.main.resourceURL?.appendingPathComponent("ARM64Runtime") else {
            throw LibraryFailure.invalid("The ARM64 runtime bundle is missing.")
        }
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: directory.appendingPathComponent("manifest.json")))
        guard manifest.major == 14, manifest.files["vcruntime140.dll"] != nil, manifest.files["msvcp140.dll"] != nil,
              manifest.version.range(of: "^v?14\\.[0-9]+\\.[0-9]+\\.[0-9]+$", options: .regularExpression) != nil else {
            throw LibraryFailure.invalid("The bundled ARM64 runtime manifest is invalid.")
        }
        for (name, hash) in manifest.files {
            guard name == URL(fileURLWithPath: name).lastPathComponent, name.hasSuffix(".dll") else { throw LibraryFailure.invalid("Invalid runtime file name.") }
            let file = directory.appendingPathComponent(name)
            let machine = try GameFiles.machine(file)
            guard machine == 0xaa64 || machine == 0xa64e else { throw LibraryFailure.invalid("Wrong runtime architecture: \(name)") }
            let actual = SHA256.hash(data: try Data(contentsOf: file)).map { String(format: "%02x", $0) }.joined()
            guard actual == hash.lowercased() else { throw LibraryFailure.invalid("Runtime checksum mismatch: \(name)") }
        }
        guard spc_install_arm64_runtime(prefix.path) == 0 else { throw LibraryFailure.invalid("Could not install the bundled ARM64 runtime files.") }
        let prior = Dictionary(uniqueKeysWithValues: RuntimeRegistry.keys.map { ($0, RuntimeRegistry.section(in: text, key: $0)) })
        try JSONEncoder().encode(prior).write(to: backup, options: .atomic)
        let values: [(String, UInt32)] = [("Installed", 1), ("Major", manifest.major), ("Minor", manifest.minor), ("Bld", manifest.build), ("Rbld", manifest.revision)]
        var updated = text
        for registryKey in RuntimeRegistry.keys {
            var section = "[\(registryKey)]\n\"Version\"=\"\(manifest.version)\"\n"
            for (key, value) in values { section += "\"\(key)\"=dword:\(String(format: "%08x", value))\n" }
            updated = RuntimeRegistry.replacing(in: updated, with: section + "\n", key: registryKey)
        }
        try updated.write(to: registry, atomically: true, encoding: .utf8)
        SessionDiagnostics.shared.checkpoint("Verified ARM64 VC++ \(manifest.version); registered native and WOW64 views")
    }
}

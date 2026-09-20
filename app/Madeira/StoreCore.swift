import Foundation
import CryptoKit
import zlib

enum StoreFiles {
    static func destination(_ name: String, root: URL) throws -> URL {
        let normalized = name.replacingOccurrences(of: "\\", with: "/")
        let parts = normalized.split(separator: "/", omittingEmptySubsequences: false)
        guard !normalized.isEmpty, !normalized.hasPrefix("/"), !normalized.contains(":"),
              !normalized.unicodeScalars.contains(where: { $0.value < 32 }),
              parts.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }),
              normalized.utf8.count < 4096 else { throw LibraryFailure.invalid("Unsafe download path.") }
        let base = root.standardizedFileURL
        var target = base
        for part in parts {
            target.appendPathComponent(String(part))
            if (try? target.resourceValues(forKeys: [.isSymbolicLinkKey]).isSymbolicLink) == true {
                throw LibraryFailure.invalid("Install path contains a symbolic link.")
            }
        }
        guard base.resolvingSymlinksInPath().path == base.path,
              target.standardizedFileURL.path.hasPrefix(base.path + "/") else {
            throw LibraryFailure.invalid("Install destination is outside its folder.")
        }
        return target
    }

    static func hex(_ bytes: some Sequence<UInt8>) -> String {
        bytes.map { String(format: "%02x", $0) }.joined()
    }

    static func digest(_ file: URL) throws -> String {
        let handle = try FileHandle(forReadingFrom: file)
        defer { try? handle.close() }
        var hash = SHA256()
        while let data = try handle.read(upToCount: 1_048_576), !data.isEmpty { hash.update(data: data) }
        return hex(hash.finalize())
    }

    static func requireSpace(_ bytes: Int64, at url: URL) throws {
        let volume = try url.resourceValues(forKeys: [.volumeAvailableCapacityForImportantUsageKey])
        if let available = volume.volumeAvailableCapacityForImportantUsage, available < bytes {
            throw LibraryFailure.invalid("Not enough free space. Keep at least \(ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file)) free.")
        }
    }

    static func inflate(_ data: Data, windowBits: Int32 = 47, limit: Int, sink: (Data) throws -> Void) throws -> Int {
        guard data.count <= Int(UInt32.max), limit >= 0 else { throw LibraryFailure.invalid("Compressed input is too large.") }
        var stream = z_stream()
        guard inflateInit2_(&stream, windowBits, ZLIB_VERSION, Int32(MemoryLayout<z_stream>.size)) == Z_OK else {
            throw LibraryFailure.invalid("Could not initialize decompression.")
        }
        defer { inflateEnd(&stream) }
        return try data.withUnsafeBytes { raw in
            stream.next_in = UnsafeMutablePointer(mutating: raw.bindMemory(to: UInt8.self).baseAddress)
            stream.avail_in = uInt(data.count)
            var output = [UInt8](repeating: 0, count: 65_536)
            var total = 0
            while true {
                try Task.checkCancellation()
                let remaining = stream.avail_in
                let result: (Int32, Data) = output.withUnsafeMutableBufferPointer { buffer in
                    stream.next_out = buffer.baseAddress
                    stream.avail_out = uInt(buffer.count)
                    let status = zlib.inflate(&stream, Z_NO_FLUSH)
                    return (status, Data(buffer.prefix(buffer.count - Int(stream.avail_out))))
                }
                guard result.1.count <= limit - total else { throw LibraryFailure.invalid("Decompressed data exceeds its declared size.") }
                total += result.1.count
                try sink(result.1)
                if result.0 == Z_STREAM_END {
                    guard stream.avail_in == 0 else { throw LibraryFailure.invalid("Unexpected trailing compressed data.") }
                    return total
                }
                guard result.0 == Z_OK, remaining != stream.avail_in || !result.1.isEmpty else {
                    throw LibraryFailure.invalid("Truncated or invalid compressed data.")
                }
            }
        }
    }

    static func inflated(_ data: Data, limit: Int) throws -> Data {
        var result = Data()
        _ = try inflate(data, limit: limit) { result.append($0) }
        return result
    }
}

indirect enum ValveValue {
    case text(String)
    case object([String: ValveValue])
    var text: String? { if case .text(let value) = self { return value }; return nil }
    var object: [String: ValveValue]? { if case .object(let value) = self { return value }; return nil }
}

struct ValveManifest {
    struct Package: Equatable {
        let name: String
        let file: String
        let size: Int64
        let sha256: String
    }
    let version: String
    let packages: [Package]

    init(_ text: String) throws {
        guard text.utf8.count < 2_000_000 else { throw LibraryFailure.invalid("Steam manifest is too large.") }
        var parser = ValveParser(characters: Array(text))
        let values = try parser.object(nested: false, depth: 0)
        guard let client = values["win64"]?.object, let version = client["version"]?.text else {
            throw LibraryFailure.invalid("Valve did not provide a Windows 64-bit manifest.")
        }
        self.version = version
        packages = try client.compactMap { name, value in
            guard let package = value.object else { return nil }
            guard let file = package["file"]?.text, let sizeText = package["size"]?.text,
                  let size = Int64(sizeText), size > 0, size < 1_073_741_824,
                  let hash = package["sha2"]?.text,
                  file.range(of: #"^[A-Za-z0-9_]+\.zip\.[a-fA-F0-9]{40}$"#, options: .regularExpression) != nil,
                  hash.range(of: #"^[a-fA-F0-9]{64}$"#, options: .regularExpression) != nil else {
                throw LibraryFailure.invalid("Invalid Steam package metadata.")
            }
            return Package(name: name, file: file, size: size, sha256: hash.lowercased())
        }.sorted { $0.name < $1.name }
        guard !packages.isEmpty, packages.count <= 100, packages.contains(where: { $0.name == "steam_win64" }),
              packages.contains(where: { $0.name == "bins_cef_win64" }),
              packages.reduce(Int64(0), { $0 + $1.size }) < 2_147_483_648 else {
            throw LibraryFailure.invalid("Incomplete or oversized Steam manifest.")
        }
    }
}

private struct ValveParser {
    let characters: [Character]
    var offset = 0

    mutating func whitespace() {
        while offset < characters.count {
            if characters[offset].isWhitespace { offset += 1 }
            else if offset + 1 < characters.count && characters[offset] == "/" && characters[offset + 1] == "/" {
                while offset < characters.count && characters[offset] != "\n" { offset += 1 }
            } else { break }
        }
    }

    mutating func string() throws -> String {
        whitespace()
        guard offset < characters.count, characters[offset] == "\"" else { throw LibraryFailure.invalid("Invalid Valve manifest string.") }
        offset += 1
        var result = ""
        while offset < characters.count {
            let character = characters[offset]
            offset += 1
            if character == "\"" { return result }
            if character == "\\" {
                guard offset < characters.count else { break }
                result.append(characters[offset]); offset += 1
            } else { result.append(character) }
        }
        throw LibraryFailure.invalid("Unterminated Valve manifest string.")
    }

    mutating func object(nested: Bool, depth: Int) throws -> [String: ValveValue] {
        guard depth < 16 else { throw LibraryFailure.invalid("Valve manifest is too deeply nested.") }
        var result: [String: ValveValue] = [:]
        while true {
            whitespace()
            if offset == characters.count {
                guard !nested else { throw LibraryFailure.invalid("Truncated Valve manifest.") }
                return result
            }
            if characters[offset] == "}" && nested { offset += 1; return result }
            let key = try string()
            whitespace()
            guard offset < characters.count, result[key] == nil else { throw LibraryFailure.invalid("Duplicate or incomplete Valve manifest key.") }
            if characters[offset] == "{" { offset += 1; result[key] = .object(try object(nested: true, depth: depth + 1)) }
            else { result[key] = .text(try string()) }
        }
    }
}

enum StoreZIP {
    static func extract(_ archive: URL, to root: URL) throws {
        let bytes = try Data(contentsOf: archive, options: .mappedIfSafe)
        func number(_ offset: Int, _ width: Int) throws -> Int {
            guard offset >= 0, offset <= bytes.count - width else { throw LibraryFailure.invalid("Truncated ZIP header.") }
            return (0..<width).reduce(0) { $0 | Int(bytes[offset + $1]) << (8 * $1) }
        }
        guard bytes.count >= 22, bytes.count < 1_073_741_824 else { throw LibraryFailure.invalid("Invalid ZIP size.") }
        var end: Int?
        for position in stride(from: bytes.count - 22, through: max(0, bytes.count - 65_557), by: -1) {
            if try number(position, 4) == 0x06054b50,
               try position + 22 + number(position + 20, 2) == bytes.count { end = position; break }
        }
        guard let end, try number(end + 4, 2) == 0, try number(end + 6, 2) == 0,
              try number(end + 8, 2) == number(end + 10, 2) else { throw LibraryFailure.invalid("Unsupported ZIP layout.") }
        let count = try number(end + 10, 2)
        let centralSize = try number(end + 12, 4)
        let centralStart = try number(end + 16, 4)
        guard count < 65_535, centralStart <= end, centralSize == end - centralStart else {
            throw LibraryFailure.invalid("Unsupported ZIP64 or damaged directory.")
        }
        var offset = centralStart
        var total = 0
        var paths = Set<String>()
        for _ in 0..<count {
            try Task.checkCancellation()
            guard try number(offset, 4) == 0x02014b50 else { throw LibraryFailure.invalid("Invalid ZIP directory entry.") }
            let flags = try number(offset + 8, 2)
            let method = try number(offset + 10, 2)
            let checksum = try number(offset + 16, 4)
            let compressed = try number(offset + 20, 4)
            let expanded = try number(offset + 24, 4)
            let nameLength = try number(offset + 28, 2)
            let extraLength = try number(offset + 30, 2)
            let commentLength = try number(offset + 32, 2)
            let attributes = try number(offset + 38, 4)
            let local = try number(offset + 42, 4)
            let next = offset + 46 + nameLength + extraLength + commentLength
            guard next <= end, nameLength > 0, flags & 1 == 0, method == 0 || method == 8,
                  (attributes >> 16) & 0xf000 != 0xa000, try number(offset + 34, 2) == 0,
                  expanded <= 536_870_912, compressed <= 536_870_912,
                  let name = String(data: bytes.subdata(in: offset + 46..<offset + 46 + nameLength), encoding: .utf8) else {
                throw LibraryFailure.invalid("Unsupported, encrypted, linked, or oversized ZIP entry.")
            }
            total += expanded
            guard total <= 2_147_483_648, paths.insert(name.lowercased()).inserted else { throw LibraryFailure.invalid("Duplicate or oversized ZIP contents.") }
            let directory = name.hasSuffix("/")
            let destination = try StoreFiles.destination(directory ? String(name.dropLast()) : name, root: root)
            guard try number(local, 4) == 0x04034b50, try number(local + 8, 2) == method,
                  try number(local + 6, 2) == flags else { throw LibraryFailure.invalid("ZIP local header mismatch.") }
            let localNameLength = try number(local + 26, 2)
            let dataStart = try local + 30 + localNameLength + number(local + 28, 2)
            guard local < centralStart, local + 30 + localNameLength <= centralStart,
                  dataStart <= centralStart, compressed <= centralStart - dataStart,
                  bytes.subdata(in: local + 30..<local + 30 + localNameLength) == Data(name.utf8) else {
                throw LibraryFailure.invalid("ZIP data bounds mismatch.")
            }
            if directory {
                guard expanded == 0 else { throw LibraryFailure.invalid("Invalid ZIP directory size.") }
                try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
            } else {
                try FileManager.default.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
                let temporary = destination.deletingLastPathComponent().appendingPathComponent(".download-\(UUID().uuidString)")
                FileManager.default.createFile(atPath: temporary.path, contents: nil)
                let output = try FileHandle(forWritingTo: temporary)
                defer { try? output.close(); try? FileManager.default.removeItem(at: temporary) }
                var crc: uLong = 0
                func write(_ data: Data) throws {
                    crc = data.withUnsafeBytes { crc32(crc, $0.bindMemory(to: UInt8.self).baseAddress, uInt(data.count)) }
                    try output.write(contentsOf: data)
                }
                let input = bytes.subdata(in: dataStart..<dataStart + compressed)
                if method == 0 {
                    guard compressed == expanded else { throw LibraryFailure.invalid("ZIP stored size mismatch.") }
                    try write(input)
                } else {
                    guard try StoreFiles.inflate(input, windowBits: -15, limit: expanded, sink: write) == expanded else {
                        throw LibraryFailure.invalid("ZIP decompressed size mismatch.")
                    }
                }
                guard crc == checksum else { throw LibraryFailure.invalid("ZIP checksum mismatch.") }
                try output.close()
                if FileManager.default.fileExists(atPath: destination.path) {
                    _ = try FileManager.default.replaceItemAt(destination, withItemAt: temporary)
                } else { try FileManager.default.moveItem(at: temporary, to: destination) }
            }
            offset = next
        }
        guard offset == end else { throw LibraryFailure.invalid("ZIP directory size mismatch.") }
    }
}


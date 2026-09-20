import Foundation
import CryptoKit

struct GOGChunk: Decodable, Equatable {
    let compressedMd5: String
    let md5: String
    let size: Int
    let compressedSize: Int?
    func validate() throws {
        guard GOGContent.validHash(compressedMd5), GOGContent.validHash(md5),
              size >= 0, size <= 33_554_432,
              compressedSize == nil || (compressedSize! > 0 && compressedSize! <= 33_554_432) else {
            throw LibraryFailure.invalid("Invalid GOG chunk metadata.")
        }
    }
}

struct GOGFile: Equatable {
    let path: String
    let product: String
    let chunks: [GOGChunk]
    let md5: String?
    let sha256: String?
    var size: Int64 { chunks.reduce(Int64(0)) { $0 + Int64($1.size) } }
}

enum GOGContent {
    static func authorizationCode(_ url: URL, state: String) throws -> String {
        let fields = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
        guard url.scheme == "https", url.host == "embed.gog.com", url.path == "/on_login_success",
              fields.filter({ $0.name == "state" }).count == 1, fields.first(where: { $0.name == "state" })?.value == state,
              fields.filter({ $0.name == "code" }).count == 1,
              let code = fields.first(where: { $0.name == "code" })?.value, !code.isEmpty else {
            throw LibraryFailure.invalid("GOG sign-in state did not match. Please try again.")
        }
        return code
    }
    static func validHash(_ value: String, length: Int = 32) -> Bool {
        value.count == length && value.unicodeScalars.allSatisfy { "0123456789abcdefABCDEF".unicodeScalars.contains($0) }
    }
    static func identifier(_ value: Any?) -> String {
        if let value = value as? String { return value }
        if let value = value as? NSNumber { return value.stringValue }
        return ""
    }
    static func hashPath(_ hash: String) throws -> String {
        guard validHash(hash) else { throw LibraryFailure.invalid("Invalid GOG content hash.") }
        return "\(hash.prefix(2))/\(hash.dropFirst(2).prefix(2))/\(hash)"
    }
    static func chunkURL(base: URL, hash: String) throws -> URL {
        guard base.scheme == "https", base.user == nil, base.password == nil,
              var parts = URLComponents(url: base, resolvingAgainstBaseURL: false) else { throw LibraryFailure.invalid("Invalid GOG download link.") }
        while parts.percentEncodedPath.hasSuffix("/") { parts.percentEncodedPath.removeLast() }
        parts.percentEncodedPath += "/" + (try hashPath(hash))
        guard let url = parts.url else { throw LibraryFailure.invalid("Invalid GOG chunk URL.") }
        return url
    }
    static func json(_ data: Data) throws -> [String: Any] {
        let decoded = data.first(where: { ![9, 10, 13, 32].contains($0) }) == 123 ? data : try StoreFiles.inflated(data, limit: 67_108_864)
        guard let object = try JSONSerialization.jsonObject(with: decoded) as? [String: Any] else { throw LibraryFailure.invalid("Invalid GOG manifest.") }
        return object
    }

    static func files(_ object: [String: Any], product: String, root: URL) throws -> [GOGFile] {
        let depot = object["depot"] as? [String: Any] ?? object
        guard let items = depot["items"] as? [[String: Any]], items.count <= 200_000 else { throw LibraryFailure.invalid("Missing or oversized GOG depot.") }
        return try items.compactMap { item in
            guard let type = item["type"] as? String, var path = item["path"] as? String else { throw LibraryFailure.invalid("Incomplete GOG file metadata.") }
            path = path.replacingOccurrences(of: "\\", with: "/")
            if type == "DepotDirectory" {
                while path.hasSuffix("/") { path.removeLast() }
                _ = try StoreFiles.destination(path, root: root)
                try FileManager.default.createDirectory(at: StoreFiles.destination(path, root: root), withIntermediateDirectories: true)
                return nil
            }
            guard type == "DepotFile" else { throw LibraryFailure.invalid("This GOG depot contains unsupported file links or entry types.") }
            if (item["flags"] as? [String] ?? []).contains("support") { path = "__support/" + path }
            _ = try StoreFiles.destination(path, root: root)
            guard let chunksObject = item["chunks"] as? [[String: Any]] else { throw LibraryFailure.invalid("GOG file has no chunk list.") }
            let chunks = try JSONDecoder().decode([GOGChunk].self, from: JSONSerialization.data(withJSONObject: chunksObject))
            guard chunks.count <= 65_536 else { throw LibraryFailure.invalid("GOG file has too many chunks.") }
            for chunk in chunks { try chunk.validate() }
            let md5 = (item["md5"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            let sha256 = (item["sha256"] as? String).flatMap { $0.isEmpty ? nil : $0 }
            guard md5 == nil || validHash(md5!), sha256 == nil || validHash(sha256!, length: 64) else { throw LibraryFailure.invalid("Invalid GOG file hash.") }
            return GOGFile(path: path, product: product, chunks: chunks, md5: md5, sha256: sha256)
        }
    }

    static func decodeChunk(_ compressed: Data, chunk: GOGChunk) throws -> Data {
        try chunk.validate()
        guard chunk.compressedSize == nil || compressed.count == chunk.compressedSize,
              StoreFiles.hex(Insecure.MD5.hash(data: compressed)) == chunk.compressedMd5.lowercased() else {
            throw LibraryFailure.invalid("GOG compressed chunk checksum mismatch.")
        }
        let data = try StoreFiles.inflated(compressed, limit: chunk.size)
        guard data.count == chunk.size, StoreFiles.hex(Insecure.MD5.hash(data: data)) == chunk.md5.lowercased() else {
            throw LibraryFailure.invalid("GOG decompressed chunk checksum mismatch.")
        }
        return data
    }
}

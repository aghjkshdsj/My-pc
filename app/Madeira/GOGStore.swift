import SwiftUI
import WebKit
import Security
import CryptoKit

struct GOGGame: Identifiable, Codable {
    let id: String
    let title: String
    let image: URL?
}

struct GOGCredentials: Codable {
    let access: String
    let refresh: String
    let expires: Date
}

enum GOGKeychain {
    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: (Bundle.main.bundleIdentifier ?? "SomethingPC") + ".gog", kSecAttrAccount as String: "oauth"]
    }
    static func load() throws -> GOGCredentials? {
        var request = query
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data else { throw LibraryFailure.invalid("GOG Keychain is unavailable. Unlock your phone and try again.") }
        return try JSONDecoder().decode(GOGCredentials.self, from: data)
    }
    static func save(_ value: GOGCredentials) throws {
        let attributes: [String: Any] = [kSecValueData as String: try JSONEncoder().encode(value), kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        var status = SecItemUpdate(query as CFDictionary, attributes as CFDictionary)
        if status == errSecItemNotFound { status = SecItemAdd(query.merging(attributes, uniquingKeysWith: { _, new in new }) as CFDictionary, nil) }
        guard status == errSecSuccess else { throw LibraryFailure.invalid("Could not save GOG sign-in securely.") }
    }
    static func clear() throws {
        let status = SecItemDelete(query as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else { throw LibraryFailure.invalid("Could not remove GOG sign-in.") }
    }
}

actor GOGService {
    static let shared = GOGService()
    static let client = "46899977096215655"
    static let publicClientSecret = "9d85c43b1482497dbbce61f6e4aa173a433796eeae2ca8c5f6129f2dc4de46d9"
    static let redirect = "https://embed.gog.com/on_login_success?origin=client"

    static func loginURL(state: String) -> URL {
        var url = URLComponents(string: "https://auth.gog.com/auth")!
        url.queryItems = [URLQueryItem(name: "client_id", value: client), URLQueryItem(name: "redirect_uri", value: redirect),
            URLQueryItem(name: "response_type", value: "code"), URLQueryItem(name: "layout", value: "galaxy"), URLQueryItem(name: "state", value: state)]
        return url.url!
    }

    func exchange(code: String) async throws {
        _ = try await tokenRequest([URLQueryItem(name: "grant_type", value: "authorization_code"), URLQueryItem(name: "code", value: code), URLQueryItem(name: "redirect_uri", value: Self.redirect)])
    }

    private func tokenRequest(_ fields: [URLQueryItem]) async throws -> GOGCredentials {
        var url = URLComponents(string: "https://auth.gog.com/token")!
        url.queryItems = fields + [URLQueryItem(name: "client_id", value: Self.client), URLQueryItem(name: "client_secret", value: Self.publicClientSecret)]
        let response = try await StoreNetwork.json(url.url!)
        guard let access = response["access_token"] as? String, !access.isEmpty,
              let refresh = response["refresh_token"] as? String, !refresh.isEmpty,
              let lifetime = response["expires_in"] as? NSNumber, lifetime.doubleValue > 0 else { throw LibraryFailure.invalid("GOG did not return a valid sign-in token.") }
        let credentials = GOGCredentials(access: access, refresh: refresh, expires: Date().addingTimeInterval(lifetime.doubleValue))
        try GOGKeychain.save(credentials)
        return credentials
    }

    private func accessToken() async throws -> String {
        guard let credentials = try GOGKeychain.load() else { throw LibraryFailure.invalid("Sign in to GOG first.") }
        if credentials.expires.timeIntervalSinceNow > 120 { return credentials.access }
        return try await tokenRequest([URLQueryItem(name: "grant_type", value: "refresh_token"), URLQueryItem(name: "refresh_token", value: credentials.refresh)]).access
    }

    private func ownedIDs() async throws -> Set<String> {
        let data = try await StoreNetwork.json(URL(string: "https://embed.gog.com/user/data/games")!, token: accessToken())
        guard let owned = data["owned"] as? [Any], owned.count <= 20_000 else { throw LibraryFailure.invalid("GOG did not return an owned-games library.") }
        let ids = owned.map(GOGContent.identifier)
        guard ids.allSatisfy({ !$0.isEmpty && $0.allSatisfy(\.isNumber) }) else { throw LibraryFailure.invalid("Invalid GOG library identifiers.") }
        return Set(ids)
    }

    func library() async throws -> [GOGGame] {
        let ids = try await ownedIDs().sorted()
        var games: [GOGGame] = []
        for start in stride(from: 0, to: ids.count, by: 8) {
            try Task.checkCancellation()
            let batch = Array(ids[start..<min(ids.count, start + 8)])
            let found = try await withThrowingTaskGroup(of: GOGGame.self) { group in
                for id in batch {
                    group.addTask {
                        let data = try await StoreNetwork.json(URL(string: "https://api.gog.com/products/\(id)?expand=description")!)
                        let images = data["images"] as? [String: Any] ?? [:]
                        let image = (images["logo2x"] ?? images["logo"] ?? images["icon"]) as? String
                        let url = image.flatMap { URL(string: $0.hasPrefix("//") ? "https:" + $0 : $0) }
                        return GOGGame(id: id, title: data["title"] as? String ?? "GOG \(id)", image: url?.scheme == "https" ? url : nil)
                    }
                }
                var results: [GOGGame] = []
                for try await game in group { results.append(game) }
                return results
            }
            games += found
            await GOGAccount.shared.setStatus("Loaded \(games.count) of \(ids.count) games")
        }
        return games.sorted { $0.title.localizedStandardCompare($1.title) == .orderedAscending }
    }

    private func secureLinks(product: String) async throws -> [URL] {
        let response = try await StoreNetwork.json(URL(string: "https://content-system.gog.com/products/\(product)/secure_link?_version=2&generation=2&path=/")!, token: accessToken())
        guard let values = response["urls"] as? [[String: Any]] else { throw LibraryFailure.invalid("No GOG download servers were returned.") }
        let urls = values.compactMap { entry -> URL? in
            guard var template = entry["url_format"] as? String, let parameters = entry["parameters"] as? [String: Any] else { return nil }
            for (key, value) in parameters { template = template.replacingOccurrences(of: "{\(key)}", with: String(describing: value)) }
            guard !template.contains("{"), let url = URL(string: template), url.scheme == "https" else { return nil }
            return url
        }
        guard !urls.isEmpty else { throw LibraryFailure.invalid("No secure GOG download servers are available.") }
        return urls
    }

    func install(_ game: GOGGame) async throws {
        let owned = try await ownedIDs()
        guard owned.contains(game.id) else { throw LibraryFailure.invalid("This game is not owned by the signed-in GOG account.") }
        let builds = try await StoreNetwork.json(URL(string: "https://content-system.gog.com/products/\(game.id)/os/windows/builds?generation=2")!, token: accessToken())
        guard let items = builds["items"] as? [[String: Any]],
              let build = items.first(where: { ($0["generation"] as? Int) == 2 && ($0["os"] as? String) == "windows" && (($0["branch"] as? String) ?? "").isEmpty }),
              let link = build["link"] as? String, let manifestURL = URL(string: link),
              manifestURL.scheme == "https" else { throw LibraryFailure.invalid("No public Windows generation-2 build is available. Legacy generation-1/offline installers are not supported yet.") }
        await StoreInstallation.shared.update("Reading GOG manifests")
        let manifest = try GOGContent.json(await StoreNetwork.data(manifestURL))
        guard GOGContent.identifier(manifest["baseProductId"]) == game.id,
              let depots = manifest["depots"] as? [[String: Any]], !depots.isEmpty else { throw LibraryFailure.invalid("Invalid GOG base-game manifest. DLC must be installed with its base game.") }
        let manager = FileManager.default
        madeira_seed_prefix_if_needed(GameLibrary.documents.appendingPathComponent("wine").path)
        _ = try StoreFiles.destination("GOG Games", root: GameLibrary.drive)
        try manager.createDirectory(at: GameLibrary.gogFolder, withIntermediateDirectories: true)
        let safeTitle = String(game.title.map { $0.isLetter || $0.isNumber || $0 == " " || $0 == "-" ? $0 : "_" }.prefix(90))
        let destination = try StoreFiles.destination("\(safeTitle)-\(game.id)", root: GameLibrary.gogFolder)
        guard !manager.fileExists(atPath: destination.path) else { throw LibraryFailure.invalid("This GOG game folder already exists. It has not been overwritten.") }
        let work = try StoreFiles.destination(".gog-downloads", root: GameLibrary.drive)
        try manager.createDirectory(at: work, withIntermediateDirectories: true)
        let staging = try StoreFiles.destination("staging-\(UUID().uuidString)", root: work)
        let chunksFolder = try StoreFiles.destination("chunks", root: work)
        try manager.createDirectory(at: staging, withIntermediateDirectories: true)
        try manager.createDirectory(at: chunksFolder, withIntermediateDirectories: true)
        defer { try? manager.removeItem(at: staging) }
        var files: [String: GOGFile] = [:]
        var links: [String: [URL]] = [:]
        var linksTime: [String: Date] = [:]
        let matching = depots.filter { depot in
            let languages = (depot["languages"] as? [String] ?? []).map { $0.lowercased() }
            let bitness = depot["osBitness"] as? [String] ?? []
            return owned.contains(GOGContent.identifier(depot["productId"])) &&
                (languages.isEmpty || languages.contains("*") || languages.contains("en") || languages.contains("en-us")) &&
                (bitness.isEmpty || bitness.contains("64"))
        }
        guard !matching.isEmpty else { throw LibraryFailure.invalid("No owned 64-bit/neutral English GOG depots are available.") }
        for depot in matching {
            try Task.checkCancellation()
            let product = GOGContent.identifier(depot["productId"])
            guard let hash = depot["manifest"] as? String else { throw LibraryFailure.invalid("Missing GOG depot hash.") }
            let url = URL(string: "https://gog-cdn-fastly.gog.com/content-system/v2/meta/\(try GOGContent.hashPath(hash))")!
            let object = try GOGContent.json(await StoreNetwork.data(url, limit: 33_554_432))
            for file in try GOGContent.files(object, product: product, root: staging) {
                let key = file.path.lowercased()
                if let existing = files[key], existing.chunks != file.chunks { throw LibraryFailure.invalid("Conflicting GOG depots contain the same file. No installation was committed.") }
                files[key] = file
            }
            guard files.count <= 200_000 else { throw LibraryFailure.invalid("Too many GOG files.") }
        }
        guard !files.isEmpty else { throw LibraryFailure.invalid("The selected GOG depots contain no files.") }
        let total = files.values.reduce(Int64(0)) { $0 + $1.size }
        guard total <= 536_870_912_000 else { throw LibraryFailure.invalid("GOG installation is too large.") }
        try StoreFiles.requireSpace(total * 2 + 536_870_912, at: work)
        var completed: Int64 = 0
        for file in files.values.sorted(by: { $0.path < $1.path }) {
            try Task.checkCancellation()
            let target = try StoreFiles.destination(file.path, root: staging)
            try manager.createDirectory(at: target.deletingLastPathComponent(), withIntermediateDirectories: true)
            manager.createFile(atPath: target.path, contents: nil)
            let handle = try FileHandle(forWritingTo: target)
            defer { try? handle.close() }
            var fileMD5 = Insecure.MD5()
            var fileSHA = SHA256()
            for chunk in file.chunks {
                try Task.checkCancellation()
                let cached = try StoreFiles.destination(chunk.compressedMd5.lowercased(), root: chunksFolder)
                var decoded: Data?
                if let existing = try? Data(contentsOf: cached, options: .mappedIfSafe) { decoded = try? GOGContent.decodeChunk(existing, chunk: chunk) }
                if decoded == nil {
                    if linksTime[file.product] == nil || Date().timeIntervalSince(linksTime[file.product]!) > 900 {
                        links[file.product] = try await secureLinks(product: file.product)
                        linksTime[file.product] = Date()
                    }
                    var lastError: Error = LibraryFailure.invalid("GOG download unavailable.")
                    for base in links[file.product] ?? [] {
                        do {
                            let bytes = try await StoreNetwork.data(GOGContent.chunkURL(base: base, hash: chunk.compressedMd5), limit: Int64(chunk.compressedSize ?? 33_554_432))
                            decoded = try GOGContent.decodeChunk(bytes, chunk: chunk)
                            try bytes.write(to: cached, options: .atomic)
                            break
                        } catch { lastError = error; try Task.checkCancellation() }
                    }
                    guard decoded != nil else { throw lastError }
                }
                let bytes = decoded!
                try handle.write(contentsOf: bytes)
                fileMD5.update(data: bytes); fileSHA.update(data: bytes)
                completed += Int64(bytes.count)
                await StoreInstallation.shared.update("Installing \(game.title)", completed: completed, total: total)
            }
            guard file.md5 == nil || StoreFiles.hex(fileMD5.finalize()) == file.md5?.lowercased(),
                  file.sha256 == nil || StoreFiles.hex(fileSHA.finalize()) == file.sha256?.lowercased() else {
                throw LibraryFailure.invalid("GOG file checksum mismatch: \(file.path)")
            }
            try handle.close()
        }
        try Task.checkCancellation()
        let metadata: [String: Any] = ["productID": game.id, "title": game.title, "build": GOGContent.identifier(build["build_id"]),
            "dependencies": manifest["dependencies"] as? [String] ?? [], "scriptInterpreter": manifest["scriptInterpreter"] as? Bool ?? false,
            "note": "Game files verified. Automatic post-install scripts, prerequisite installers and cloud saves are not implemented."]
        try JSONSerialization.data(withJSONObject: metadata, options: .prettyPrinted).write(to: staging.appendingPathComponent("somethingpc-gog-install.json"))
        try manager.moveItem(at: staging, to: destination)
        SessionDiagnostics.shared.event("GOG game files installed and verified: \(game.title). Post-install prerequisites may still be required.")
    }
}

@MainActor final class GOGAccount: ObservableObject {
    static let shared = GOGAccount()
    @Published private(set) var connected = false
    @Published private(set) var busy = false
    @Published private(set) var games: [GOGGame] = []
    @Published private(set) var status = ""
    @Published var error: String?
    private init() {
        do { connected = try GOGKeychain.load() != nil }
        catch { self.error = error.localizedDescription }
    }
    func setStatus(_ value: String) { status = value }
    func complete(code: String) {
        guard !busy else { return }
        busy = true
        error = nil
        Task {
            do {
                try await GOGService.shared.exchange(code: code)
                connected = true
                games = try await GOGService.shared.library()
                status = "\(games.count) owned games"
            } catch { self.error = error.localizedDescription }
            busy = false
        }
    }
    func refresh() {
        guard connected, !busy else { return }
        busy = true
        error = nil
        Task {
            do { games = try await GOGService.shared.library(); status = "\(games.count) owned games" }
            catch { self.error = error.localizedDescription }
            busy = false
        }
    }
    func signOut() {
        guard !busy, !StoreInstallation.shared.busy else { return }
        do { try GOGKeychain.clear(); connected = false; games = []; status = "" }
        catch { self.error = error.localizedDescription }
    }
}

struct GOGLoginView: UIViewRepresentable {
    let state: String
    let completion: (Result<String, Error>) -> Void
    func makeCoordinator() -> Coordinator { Coordinator(state: state, completion: completion) }
    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.load(URLRequest(url: GOGService.loginURL(state: state)))
        return view
    }
    func updateUIView(_ uiView: WKWebView, context: Context) {}
    final class Coordinator: NSObject, WKNavigationDelegate {
        let state: String
        let completion: (Result<String, Error>) -> Void
        private var finished = false
        init(state: String, completion: @escaping (Result<String, Error>) -> Void) { self.state = state; self.completion = completion }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url, url.scheme == "https" else { decisionHandler(.cancel); return }
            if url.host == "embed.gog.com" && url.path == "/on_login_success" {
                decisionHandler(.cancel)
                guard !finished else { return }
                finished = true
                let fields = URLComponents(url: url, resolvingAgainstBaseURL: false)?.queryItems ?? []
                guard fields.filter({ $0.name == "state" }).count == 1, fields.first(where: { $0.name == "state" })?.value == state,
                      fields.filter({ $0.name == "code" }).count == 1,
                      let code = fields.first(where: { $0.name == "code" })?.value, !code.isEmpty else {
                    completion(.failure(LibraryFailure.invalid("GOG sign-in state did not match. Please try again."))); return
                }
                completion(.success(code))
            } else { decisionHandler(.allow) }
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            guard !finished, (error as NSError).code != NSURLErrorCancelled else { return }
            finished = true
            completion(.failure(LibraryFailure.invalid("GOG sign-in could not load. Check your connection and try again.")))
        }
    }
}


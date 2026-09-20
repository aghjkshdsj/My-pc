import Foundation
import Security
import CommonCrypto

struct LocalAccountRecord: Codable {
    var username: String
    var salt: Data
    var verifier: Data
    var rounds: UInt32 = 600_000
    var remember = false
    var failures = 0
    var blockedUntil: Date?

    static func create(username: String, password: String) throws -> Self {
        guard !username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              username.utf8.count <= 80, password.utf8.count >= 6, password.utf8.count <= 1024 else {
            throw LibraryFailure.invalid("Enter a username and a password of at least six characters.")
        }
        var salt = Data(count: 32)
        let status = salt.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, 32, $0.baseAddress!) }
        guard status == errSecSuccess else { throw LibraryFailure.invalid("Could not generate secure account data.") }
        var record = Self(username: username, salt: salt, verifier: Data())
        record.verifier = try record.derive(password)
        return record
    }

    private func derive(_ password: String) throws -> Data {
        guard salt.count == 32, rounds == 600_000, password.utf8.count <= 1024 else { throw LibraryFailure.invalid("Invalid local account data.") }
        let passwordBytes = Array(password.utf8)
        var output = Data(count: 32)
        let status = output.withUnsafeMutableBytes { outputBytes in
            salt.withUnsafeBytes { saltBytes in
                passwordBytes.withUnsafeBytes { input in
                    CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2), input.baseAddress?.assumingMemoryBound(to: Int8.self), input.count,
                        saltBytes.baseAddress?.assumingMemoryBound(to: UInt8.self), saltBytes.count,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), rounds,
                        outputBytes.baseAddress?.assumingMemoryBound(to: UInt8.self), outputBytes.count)
                }
            }
        }
        guard status == kCCSuccess else { throw LibraryFailure.invalid("Password verification failed.") }
        return output
    }

    mutating func authenticate(username: String, password: String, remember: Bool, now: Date = Date()) throws -> Bool {
        guard blockedUntil.map({ $0 <= now }) ?? true else { throw LibraryFailure.invalid("Too many attempts. Wait 30 seconds and try again.") }
        let candidate = try derive(password)
        let matches = verifier.count == candidate.count && zip(verifier, candidate).reduce(UInt8(0)) { $0 | ($1.0 ^ $1.1) } == 0
        if matches && self.username == username {
            failures = 0
            blockedUntil = nil
            self.remember = remember
            return true
        }
        failures += 1
        self.remember = false
        if failures >= 5 { failures = 0; blockedUntil = now.addingTimeInterval(30) }
        return false
    }
}

enum LocalAccountKeychain {
    private static var query: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: (Bundle.main.bundleIdentifier ?? "com.madeira.emulator") + ".local-account",
         kSecAttrAccount as String: "primary"]
    }
    static func load() throws -> LocalAccountRecord? {
        var request = query
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let data = result as? Data else {
            throw LibraryFailure.invalid("The local account Keychain is unavailable (\(status)). Unlock your iPhone and reopen the app.")
        }
        return try JSONDecoder().decode(LocalAccountRecord.self, from: data)
    }
    static func save(_ record: LocalAccountRecord) throws {
        let values: [String: Any] = [kSecValueData as String: try JSONEncoder().encode(record),
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly]
        var status = SecItemUpdate(query as CFDictionary, values as CFDictionary)
        if status == errSecItemNotFound {
            var item = query
            values.forEach { item[$0.key] = $0.value }
            status = SecItemAdd(item as CFDictionary, nil)
        }
        guard status == errSecSuccess else { throw LibraryFailure.invalid("Could not save the local account securely (\(status)).") }
    }
}

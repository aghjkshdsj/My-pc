import SwiftUI

@MainActor final class LocalAccount: ObservableObject {
    static let shared = LocalAccount()
    @Published private(set) var unlocked = false
    @Published private(set) var configured = false
    @Published private(set) var remembered = false
    @Published private(set) var username = "Dan"
    @Published private(set) var busy = false
    @Published private(set) var unavailable = false
    @Published var error: String?

    private init() {
        do {
            if let record = try LocalAccountKeychain.load() {
                configured = true
                username = record.username
                remembered = record.remember
                unlocked = record.remember
            }
        } catch { self.error = error.localizedDescription; unavailable = true }
    }

    func submit(username: String, password: String, remember: Bool) {
        guard !busy, !unavailable else { return }
        busy = true
        error = nil
        let creating = !configured
        Task {
            do {
                let record = try await Task.detached(priority: .userInitiated) {
                    var record: LocalAccountRecord
                    if creating {
                        guard try LocalAccountKeychain.load() == nil else { throw LibraryFailure.invalid("An account already exists. Reopen the app to sign in.") }
                        record = try LocalAccountRecord.create(username: username, password: password)
                        record.remember = remember
                    } else {
                        guard var existing = try LocalAccountKeychain.load() else { throw LibraryFailure.invalid("Account data is missing. Reopen the app.") }
                        let authenticated = try existing.authenticate(username: username, password: password, remember: remember)
                        try LocalAccountKeychain.save(existing)
                        guard authenticated else { throw LibraryFailure.invalid("Incorrect username or password.") }
                        record = existing
                    }
                    try LocalAccountKeychain.save(record)
                    return record
                }.value
                self.username = record.username
                configured = true
                remembered = record.remember
                unlocked = true
            } catch { self.error = error.localizedDescription }
            busy = false
        }
    }

    func rememberSignIn(_ value: Bool) {
        guard unlocked else { return }
        do {
            guard var record = try LocalAccountKeychain.load() else { throw LibraryFailure.invalid("Account data is missing.") }
            record.remember = value
            try LocalAccountKeychain.save(record)
            remembered = value
        } catch { self.error = error.localizedDescription }
    }
}

struct AccountRootView: View {
    @ObservedObject private var account = LocalAccount.shared
    var body: some View {
        if account.unlocked { ContentView() }
        else { LocalSignInView() }
    }
}

struct LocalSignInView: View {
    @ObservedObject private var account = LocalAccount.shared
    @State private var username = "Dan"
    @State private var password = ""
    @State private var confirmation = ""
    @State private var remember = false
    var body: some View {
        NavigationStack {
            Form {
                Section(account.configured ? "Local sign-in" : "Create your local account") {
                    TextField("Username", text: $username).textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("Password", text: $password).textContentType(account.configured ? .password : .newPassword)
                    if !account.configured { SecureField("Confirm password", text: $confirmation).textContentType(.newPassword) }
                    Toggle("Save credentials", isOn: $remember)
                    Button(account.configured ? "Sign in" : "Create account") {
                        account.submit(username: username, password: password, remember: remember)
                        password = ""
                        confirmation = ""
                    }.disabled(account.busy || account.unavailable || password.isEmpty || (!account.configured && password != confirmation))
                    if account.busy { ProgressView("Verifying…") }
                    if let error = account.error { Text(error).foregroundStyle(.red) }
                }
                Section {
                    Text("Set your chosen password once on this iPhone. Password verification and remembered sign-in stay in iOS Keychain; no password is bundled in the app or uploaded.")
                    Text("This is a local launch lock, not an online account or encryption for game files. Saved credentials skip the lock on later launches. Keep your password safe; there is no online password recovery.")
                }.font(.caption).foregroundStyle(.secondary)
            }
            .navigationTitle("Something PC")
            .onAppear { username = account.username }
        }.preferredColorScheme(.dark)
    }
}

struct LocalAccountSettingsView: View {
    @ObservedObject private var account = LocalAccount.shared
    var body: some View {
        Form {
            LabeledContent("Local username", value: account.username)
            LabeledContent("Remembered sign-in", value: account.remembered ? "On" : "Off")
            Button("Save credentials") { account.rememberSignIn(true) }
            Button("Require password on next app launch") { account.rememberSignIn(false) }
            Text("This does not interrupt your running game. Your local account is separate from Steam and GOG. Game documents are not encrypted by this lock.")
                .font(.caption).foregroundStyle(.secondary)
            if let error = account.error { Text(error).foregroundStyle(.red) }
        }.navigationTitle("Local Account")
    }
}

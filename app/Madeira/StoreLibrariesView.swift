import SwiftUI

struct StoreLibrariesView: View {
    @ObservedObject private var library = GameLibrary.shared
    @ObservedObject private var installation = StoreInstallation.shared
    @ObservedObject private var gog = GOGAccount.shared
    @State private var login: LoginAttempt?
    @State private var steamConfirmation = false
    @State private var selectedGame: GOGGame?
    @State private var importing = false
    @State private var destination = GameLibrary.steamFolder
    @State private var search = ""
    private struct LoginAttempt: Identifiable { let id = UUID().uuidString }
    var body: some View {
        Form {
            if installation.busy || !installation.phase.isEmpty || installation.error != nil {
                Section(installation.title.isEmpty ? "Installer" : installation.title) {
                    Text(installation.phase)
                    if installation.total > 0 {
                        ProgressView(value: Double(installation.completed), total: Double(installation.total))
                        Text("\(ByteCountFormatter.string(fromByteCount: installation.completed, countStyle: .file)) / \(ByteCountFormatter.string(fromByteCount: installation.total, countStyle: .file))")
                            .font(.caption).monospacedDigit()
                    } else if installation.busy { ProgressView() }
                    if let error = installation.error { Text(error).foregroundStyle(.red) }
                    if installation.busy { Button("Cancel installation", role: .destructive) { installation.cancel() } }
                }
            }
            Section("Steam on your phone") {
                Label(SteamInstaller.isInstalled ? "64-bit client installed" : "Install the 64-bit Windows client", systemImage: "desktopcomputer")
                Button(SteamInstaller.isInstalled ? "Repair / update Steam client" : "Download & install Steam") { steamConfirmation = true }
                    .disabled(installation.busy || gog.busy)
                Text("Downloads official Valve packages, verifies SHA-256, and installs into C:\\Steam without SteamSetup.exe. Keep roughly 2 GB free and use Wi-Fi.")
                Text("Then tap Steam in Library: Windows desktop opens first, followed by Steam. Sign in there, including Steam Guard, and install owned games to the default C:\\Steam\\steamapps\\common folder. Refresh Library after downloads finish.")
                Text("Experimental: this is the real Steam client inside Wine, not GameNative’s native Steam library API. CEF rendering, login, client updates, DRM and individual games may still fail on iOS. Signing in is not proof of game compatibility.")
                    .foregroundStyle(.secondary)
            }.font(.callout)
            Section("GOG library & downloads") {
                if gog.connected {
                    HStack {
                        Button("Refresh owned games") { gog.refresh() }
                        Spacer()
                        Button("Sign out", role: .destructive) { gog.signOut() }
                    }.disabled(gog.busy || installation.busy)
                    if gog.busy { ProgressView(gog.status.isEmpty ? "Loading your GOG library…" : gog.status) }
                    else { Text(gog.status).font(.caption).foregroundStyle(.secondary) }
                    ForEach(gog.games.filter { search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) }) { game in
                        HStack {
                            AsyncImage(url: game.image) { image in image.resizable().scaledToFit() } placeholder: { Image(systemName: "gamecontroller") }
                                .frame(width: 52, height: 42).clipShape(RoundedRectangle(cornerRadius: 6))
                            Text(game.title)
                            Spacer()
                            Button { selectedGame = game } label: { Image(systemName: "arrow.down.circle") }
                                .accessibilityLabel("Install \(game.title)")
                                .disabled(gog.busy || installation.busy)
                        }
                    }
                } else {
                    Button("Sign in to GOG") { login = LoginAttempt() }.disabled(gog.busy || installation.busy)
                }
                if let error = gog.error { Text(error).foregroundStyle(.red) }
                Text("Official GOG login stays in an isolated web view; Something PC saves OAuth tokens in iOS Keychain, not your password. Download owned Windows generation-2 games directly into C:\\GOG Games. English/64-bit-compatible depots only; chunk and file checksums are verified.")
                Text("Legacy generation-1 downloads, post-install scripts, automatic prerequisites, cloud saves and updates are not implemented. Some installed games still need additional setup or are incompatible with this runtime. Downloads require the app to remain open; cancel/retry reuses verified GOG chunks.")
                    .foregroundStyle(.secondary)
            }.font(.callout)
            Section("Import existing installations") {
                Button("Import installed Steam game folder") { destination = GameLibrary.steamFolder; importing = true }
                Button("Import installed GOG game folder") { destination = GameLibrary.gogFolder; importing = true }
                Text("Optional: copy an already-installed game from Files. This is separate from the in-app downloads above.")
                    .font(.caption).foregroundStyle(.secondary)
            }.disabled(library.busy || installation.busy)
            Text("Restart Something PC before installing if a Windows session has already started. Favorites sort first, then foreground session playtime; time spent in Library or in the background is not counted.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .navigationTitle("Steam & GOG")
        .searchable(text: $search, prompt: "Search owned GOG games")
        .sheet(item: $login) { attempt in
            NavigationStack {
                GOGLoginView(state: attempt.id) { result in
                    login = nil
                    switch result {
                    case .success(let code): gog.complete(code: code)
                    case .failure(let error): gog.error = error.localizedDescription
                    }
                }.navigationTitle("Sign in · gog.com")
                    .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Cancel") { login = nil } } }
            }
        }
        .alert("Install official Steam client?", isPresented: $steamConfirmation) {
            Button("Download & install") { installation.start("Steam") { try await SteamInstaller.install() } }
            Button("Cancel", role: .cancel) {}
        } message: { Text("About 350 MB to download; allow at least 2 GB of free space. Your existing steamapps, userdata and config folders are preserved. Game purchases are never made automatically.") }
        .alert("Install \(selectedGame?.title ?? "GOG game")?", isPresented: Binding(get: { selectedGame != nil }, set: { if !$0 { selectedGame = nil } })) {
            if let game = selectedGame {
                Button("Install game files") {
                    selectedGame = nil
                    installation.start(game.title) { try await GOGService.shared.install(game) }
                }
            }
            Button("Cancel", role: .cancel) { selectedGame = nil }
        } message: { Text("Download this owned game's Windows files to your phone. Downloads can be large. A free-space check runs before downloading; no purchase is made. Post-install prerequisites may still be needed.") }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.folder]) { result in
            library.importGame(result.map { [$0] }, folder: true, destination: destination)
        }
    }
}

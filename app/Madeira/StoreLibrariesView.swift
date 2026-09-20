import SwiftUI
import SafariServices

struct StoreLibrariesView: View {
    @ObservedObject private var library = GameLibrary.shared
    @State private var browser: StoreSite?
    @State private var importing = false
    @State private var destination = GameLibrary.steamFolder
    private struct StoreSite: Identifiable {
        let id = UUID()
        let url: URL
    }
    var body: some View {
        Form {
            Section("Current support") {
                Text("Website sign-in and importing already-installed Windows game folders are available. Native Steam/GOG library sync, game downloading, installer extraction, updates, and cloud saves are not implemented in this iOS build.")
                    .font(.callout)
                Text("Website login is not a connection to the Windows Steam client. Do not enter store passwords into the Something PC local-account screen.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("Steam") {
                Button("Open official Steam website") { browser = StoreSite(url: URL(string: "https://store.steampowered.com/login/")!) }
                Button("Import installed Steam game folder") { destination = GameLibrary.steamFolder; importing = true }
                Text("Destination: C:\\Steam\\steamapps\\common\nCopy an installed Windows game from your own library. Games requiring the Steam client or DRM may not run. The normal 32-bit Steam installer is not supported by this 64-bit runtime.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Section("GOG") {
                Button("Open official GOG library") { browser = StoreSite(url: URL(string: "https://www.gog.com/account")!) }
                Button("Import installed GOG game folder") { destination = GameLibrary.gogFolder; importing = true }
                Text("Destination: C:\\GOG Games\nImport a complete, already-installed Windows game folder, not just a GOG setup EXE. Offline installers and their BIN parts are not ready-to-play games; this app does not currently extract them.")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if library.busy { ProgressView("Importing and indexing…") }
            Text("Import preserves the source folder. Refresh library after moving files manually. Downloading a title does not guarantee Wine/FEX/Metal compatibility.")
                .font(.caption).foregroundStyle(.secondary)
        }
        .navigationTitle("Steam & GOG")
        .disabled(library.busy)
        .sheet(item: $browser) { StoreBrowser(url: $0.url) }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.folder]) { result in
            library.importGame(result.map { [$0] }, folder: true, destination: destination)
        }
    }
}

private struct StoreBrowser: UIViewControllerRepresentable {
    let url: URL
    func makeUIViewController(context: Context) -> SFSafariViewController { SFSafariViewController(url: url) }
    func updateUIViewController(_ controller: SFSafariViewController, context: Context) {}
}

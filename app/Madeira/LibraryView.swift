import SwiftUI
import UniformTypeIdentifiers
import UIKit
import ImageIO

final class GameLibrary: ObservableObject {
    static let shared = GameLibrary()
    static let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].resolvingSymlinksInPath().standardizedFileURL
    static let drive = documents.appendingPathComponent("wine/drive_c", isDirectory: true)
    static let gamesFolder = drive.appendingPathComponent("Games", isDirectory: true)
    static let steamFolder = drive.appendingPathComponent("Steam/steamapps/common", isDirectory: true)
    static let gogFolder = drive.appendingPathComponent("GOG Games", isDirectory: true)
    @Published private(set) var games: [LibraryGame] = [.pc, .steam]
    @Published private(set) var steamClient: SteamClientInstallation?
    var apps: [LibraryGame] { SteamClientInstallation.libraryApps(for: steamClient) }
    @Published private(set) var scannedAt: Date?
    @Published var busy = false
    @Published var error: String?
    @Published var sessionStarted = false
    private var profiles: [String: GameProfile] = [:]
    private var launchers: [String: String] = [:]
    private var hidden: Set<String> = []
    private var indexedGames: [LibraryGame] = []
    private var loaded = false
    private var activity: [String: GameActivity] = [:]
    private let activityURL = documents.appendingPathComponent("somethingpc-playtime.json")
    private let indexURL = documents.appendingPathComponent("somethingpc-library-index.json")
    private let profilesURL = documents.appendingPathComponent("somethingpc-games.json")
    private let launchersURL = documents.appendingPathComponent("somethingpc-launchers.json")

    private init() {
        if let data = try? Data(contentsOf: activityURL) {
            if let saved = try? JSONDecoder().decode([String: GameActivity].self, from: data),
               saved.values.allSatisfy({ $0.seconds.isFinite && $0.seconds >= 0 }) { activity = saved }
            else { try? data.write(to: Self.documents.appendingPathComponent("playtime-backup-\(UUID().uuidString).json"), options: .atomic) }
        }
        if let data = try? Data(contentsOf: launchersURL), let saved = try? JSONDecoder().decode([String: String].self, from: data) { launchers = saved }
        hidden = Set(UserDefaults.standard.stringArray(forKey: "hiddenLibraryGames") ?? [])
        if let data = try? Data(contentsOf: profilesURL) {
            do { profiles = try JSONDecoder().decode([String: GameProfile].self, from: data) }
            catch {
                try? data.write(to: Self.documents.appendingPathComponent("game-settings-backup-\(UUID().uuidString).json"), options: .atomic)
                self.error = "Could not read game settings; a backup was preserved. \(error.localizedDescription)"
            }
        }
    }

    func profile(for game: LibraryGame) -> GameProfile {
        if let profile = profiles[game.id] { return profile }
        if let executable = game.executable, GameFiles.isInside(executable, root: Self.gamesFolder) {
            let legacyID = String(executable.path.dropFirst(Self.gamesFolder.path.count + 1))
            if let profile = profiles[legacyID] { return profile }
        }
        let settings = EmulatorSettings.shared
        let input = InputSettings.shared
        var profile = GameProfile()
        profile.resolution = settings.resolution
        profile.showFPS = settings.showFPS
        profile.presentationMode = settings.presentationMode
        profile.keepAwake = settings.keepAwake
        profile.controllerMode = settings.controllerMode
        profile.deadZone = settings.deadZone
        profile.mouseSpeed = settings.mouseSpeed
        profile.relativeMouse = input.relative
        profile.pointerSensitivity = input.sensAbs
        profile.mouseLookSensitivity = input.sensRel
        profile.diagnostics = input.diagnostics
        return profile
    }

    func save(_ profile: GameProfile, for game: LibraryGame) {
        var updated = profiles
        updated[game.id] = profile
        do {
            try JSONEncoder().encode(updated).write(to: profilesURL, options: .atomic)
            profiles = updated
            objectWillChange.send()
        } catch { self.error = error.localizedDescription }
    }

    func loadSavedLibrary() {
        refreshSteamClient()
        guard !loaded, !busy else { return }
        loaded = true
        guard FileManager.default.fileExists(atPath: indexURL.path) else { refresh(); return }
        busy = true
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Result { try LibraryIndex.read(self.indexURL, drive: Self.drive) }
            DispatchQueue.main.async {
                self.busy = false
                switch result {
                case .success(let saved):
                    self.indexedGames = saved.games
                    self.scannedAt = saved.date
                    self.applyIndex()
                case .failure(let error): self.error = "Could not load the saved library: \(error.localizedDescription) Use Refresh library to rescan. Your games have not been changed."
                }
            }
        }
    }

    private func applyIndex() {
        games = GameActivity.sorted(apps + indexedGames.filter { !$0.isDesktop && !hidden.contains($0.id) }.map(resolve), activity: activity)
        SessionDiagnostics.shared.libraryInventory(games)
    }

    /// A bounded check of Steam client locations, independent of scanning game folders.
    func refreshSteamClient() {
        steamClient = SteamInstaller.installedClients.first
        applyIndex()
    }

    func activity(for game: LibraryGame) -> GameActivity { activity[game.id] ?? GameActivity() }

    func toggleFavorite(_ game: LibraryGame) {
        var entry = activity(for: game)
        entry.favorite.toggle()
        saveActivity(entry, id: game.id)
    }

    func addPlaytime(_ seconds: Double, id: String) {
        guard seconds.isFinite, seconds > 0 else { return }
        var entry = activity[id] ?? GameActivity()
        entry.seconds += seconds
        saveActivity(entry, id: id)
    }

    private func saveActivity(_ entry: GameActivity, id: String) {
        var updated = activity
        updated[id] = entry
        do {
            try JSONEncoder().encode(updated).write(to: activityURL, options: .atomic)
            activity = updated
            games = GameActivity.sorted(games, activity: activity)
        } catch { self.error = "Could not save favorites/playtime: \(error.localizedDescription)" }
    }

    func refresh() {
        refreshSteamClient()
        guard !busy else { return }
        busy = true
        DispatchQueue.global(qos: .userInitiated).async {
            let result = Result { () throws -> LibraryIndex in
                var found = try GameFiles.discover(in: Self.gamesFolder)
                for directory in SteamInstaller.libraryDirectories {
                    found += try SteamLibraryCatalog.discoverGames(in: directory, drive: Self.drive)
                }
                for (prefix, folder) in [("gog:", Self.gogFolder)] {
                    found += try GameFiles.discover(in: folder).map { game in
                        var entry = LibraryGame(id: prefix + game.id, title: game.title, publisher: "GOG", executable: game.executable, cover: game.cover, steamID: game.steamID)
                        entry.candidates = game.candidates
                        entry.folder = game.folder
                        return entry
                    }
                }
                let index = try LibraryIndex(games: found, drive: Self.drive)
                try index.write(to: self.indexURL)
                return index
            }
            DispatchQueue.main.async {
                self.busy = false
                switch result {
                case .success(let index):
                    do {
                        self.indexedGames = try index.games(in: Self.drive)
                        self.scannedAt = index.scannedAt
                        self.loaded = true
                        self.applyIndex()
                    } catch { self.error = error.localizedDescription }
                case .failure(let error): self.error = error.localizedDescription
                }
            }
        }
    }

    private func resolve(_ game: LibraryGame) -> LibraryGame {
        guard let relative = launchers[game.id], let selected = game.candidates.first(where: {
            Self.launcherPath($0) == relative || (try? LibraryIndex.relative($0, to: Self.drive)) == relative
        }) else { return game }
        var updated = LibraryGame(id: game.id, title: game.title,
            publisher: game.publisher, executable: selected, cover: game.cover, steamID: game.steamID)
        updated.candidates = game.candidates
        updated.folder = game.folder
        return updated
    }

    func selectExecutable(_ relative: String, for game: LibraryGame) throws {
        var updated = launchers
        if relative.isEmpty { updated.removeValue(forKey: game.id) }
        else {
            guard let selected = game.candidates.first(where: { Self.launcherPath($0) == relative }) else {
                throw LibraryFailure.invalid("Choose one of this game's executable files.")
            }
            _ = try GameFiles.gameExecutableMachine(selected)
            updated[game.id] = try LibraryIndex.relative(selected, to: Self.drive)
        }
        try JSONEncoder().encode(updated).write(to: launchersURL, options: .atomic)
        launchers = updated
        applyIndex()
    }

    static func launcherPath(_ file: URL) -> String {
        (try? LibraryIndex.relative(file, to: GameFiles.isInside(file, root: gamesFolder) ? gamesFolder : drive)) ?? file.lastPathComponent
    }

    func hide(_ game: LibraryGame) {
        guard !game.isDesktop else { return }
        hidden.insert(game.id)
        UserDefaults.standard.set(Array(hidden), forKey: "hiddenLibraryGames")
        games.removeAll { $0.id == game.id }
    }

    func restoreHidden() {
        hidden.removeAll()
        UserDefaults.standard.removeObject(forKey: "hiddenLibraryGames")
        applyIndex()
    }

    func importGame(_ result: Result<[URL], Error>, folder: Bool, destination: URL? = nil) {
        guard case .success(let urls) = result, let source = urls.first else {
            if case .failure(let error) = result { self.error = error.localizedDescription }
            return
        }
        busy = true
        DispatchQueue.global(qos: .userInitiated).async {
            let accessed = source.startAccessingSecurityScopedResource()
            defer { if accessed { source.stopAccessingSecurityScopedResource() } }
            var coordinationError: NSError?
            var failure: Error?
            NSFileCoordinator().coordinate(readingItemAt: source, options: [], error: &coordinationError) { url in
                do { try GameFiles.copyImport(url, to: destination ?? Self.gamesFolder, folder: folder) }
                catch { failure = error }
            }
            let message = (failure ?? coordinationError)?.localizedDescription
            DispatchQueue.main.async {
                self.busy = false
                if let message { self.error = message } else { self.refresh() }
            }
        }
    }
}

struct LibraryView: View {
    let launch: (LibraryGame, GameProfile) -> Void
    let resume: () -> Void
    let diagnostics: () -> Void
    @Environment(\.scenePhase) private var scenePhase
    @ObservedObject private var library = GameLibrary.shared
    @ObservedObject private var recovery = CrashRecovery.shared
    @State private var settingsTab = false
    @State private var importing = false
    @State private var importFolder = false
    @State private var exeWarning = false
    @State private var selectedGame: LibraryGame?
    @State private var sharing = false
    @State private var supportPresented = false
    @State private var storesPresented = false
    @State private var linuxPresented = false

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .bottom) {
                Color.black.ignoresSafeArea()
                if settingsTab {
                    EmulatorSettingsView(showDone: false)
                        .padding(.bottom, 88)
                } else {
                    VStack(spacing: 12) {
                        header
                        ScrollView {
                            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 20), count: geometry.size.width > geometry.size.height ? 4 : 2), spacing: 20) {
                                Section {
                                    ForEach(library.apps) { game in libraryCard(game) }
                                    if LinuxVMSession.framework != nil {
                                        Button { linuxPresented = true } label: {
                                            VStack(spacing: 12) {
                                                Image(systemName: "desktopcomputer").font(.largeTitle)
                                                Text("Linux ARM64").font(.headline)
                                                Text("Development preview").font(.caption).foregroundStyle(.secondary)
                                            }
                                            .frame(maxWidth: .infinity, minHeight: 180)
                                            .background(.white.opacity(0.08), in: RoundedRectangle(cornerRadius: 20))
                                        }.buttonStyle(.plain)
                                    }
                                } header: {
                                    Text("Apps").font(.headline).frame(maxWidth: .infinity, alignment: .leading)
                                }
                                Section {
                                    ForEach(library.games.filter { !$0.isDesktop }) { game in libraryCard(game) }
                                } header: {
                                    Text("Games").font(.headline).frame(maxWidth: .infinity, alignment: .leading)
                                }
                            }
                            .padding(.horizontal, geometry.size.width > 700 ? 40 : 20)
                            .padding(.top, 12)
                            .padding(.bottom, 110)
                            if !library.games.contains(where: { !$0.isDesktop }) {
                                Text("Steam is always in Apps above. Install it there, then use Steam to download games and Refresh library. You can also import game folders with +. Library checks C:\\Games, detected Steam game folders, and C:\\GOG Games.")
                                    .font(.callout).foregroundStyle(.secondary).padding().padding(.bottom, 100)
                            }
                        }
                        .refreshable { library.refresh() }
                    }
                }
                HStack(spacing: 8) {
                    tab("Library", icon: "gamecontroller.fill", selected: !settingsTab) { settingsTab = false }
                    tab("Settings", icon: "gearshape", selected: settingsTab) { settingsTab = true }
                }
                .padding(8).background(.ultraThinMaterial, in: Capsule())
                .overlay(Capsule().stroke(Color.white.opacity(0.15)))
                .padding(.bottom, 12)
                if library.busy {
                    Color.black.opacity(0.5).ignoresSafeArea()
                    ProgressView("Preparing…").padding(24).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 20))
                        .frame(maxHeight: .infinity)
                }
            }
        }
        .preferredColorScheme(.dark)
        .onAppear { library.loadSavedLibrary() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { library.refreshSteamClient() }
        }
        .sheet(item: $selectedGame) { GameSettingsView(game: $0) }
        .fullScreenCover(isPresented: $linuxPresented) { LinuxVMView() }
        .sheet(isPresented: $storesPresented, onDismiss: { library.refreshSteamClient() }) {
            NavigationStack {
                StoreLibrariesView(openSteam: { storesPresented = false; play(.steam) })
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { storesPresented = false } } }
            }
        }
        .sheet(isPresented: $supportPresented) {
            NavigationStack { DiagnosticsView().toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { supportPresented = false } } } }
        }
        .sheet(isPresented: $sharing) {
            if let report = recovery.report { DiagnosticShareSheet(url: report) }
        }
        .fileImporter(isPresented: $importing, allowedContentTypes: importFolder ? [.folder] : [.item], allowsMultipleSelection: false) {
            library.importGame($0, folder: importFolder)
        }
        .alert("It looks like the app unexpectedly closed. Would you like to share your logs?", isPresented: $recovery.prompt) {
            Button("Close", role: .cancel) { recovery.acknowledge() }
            Button("Share") { recovery.acknowledge(); sharing = true }
        } message: {
            Text("iOS can also end the app after a force-quit or memory pressure. The report stays on your phone until you choose where to share it. Logs may contain private information.")
        }
        .alert("Custom EXE", isPresented: $exeWarning) {
            Button("Choose EXE") { importFolder = false; importing = true }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("An EXE alone may not contain the whole game. Import Game Folder is recommended to include data and DLLs. Custom EXE copies only the selected file into C:\\Games.")
        }
        .alert("Something PC", isPresented: Binding(get: { library.error != nil }, set: { if !$0 { library.error = nil } })) {
            Button("OK", role: .cancel) { library.error = nil }
        } message: { Text(library.error ?? "") }
    }

    private var header: some View {
        HStack {
            Menu {
                Button("Refresh library", systemImage: "arrow.clockwise") { library.refresh() }
                Button("Restore hidden games", systemImage: "eye") { library.restoreHidden() }
                Button("Diagnostics & JIT", systemImage: "stethoscope") { diagnostics() }
                Button("Share diagnostic report", systemImage: "square.and.arrow.up") { supportPresented = true }
                if recovery.report != nil { Button("Share last unexpected-close log", systemImage: "square.and.arrow.up") { sharing = true } }
                if library.sessionStarted { Button("Resume session", systemImage: "play.fill") { resume() } }
            } label: { Image(systemName: "ellipsis.circle").font(.title) }
            Spacer()
            Text("Library").font(.title2.bold())
            Spacer()
            Menu {
                Button("Install from Steam or GOG", systemImage: "arrow.down.circle") { storesPresented = true }
                Button("Import Game Folder", systemImage: "folder.badge.plus") { importFolder = true; importing = true }
                Button("Custom EXE", systemImage: "doc.badge.plus") { exeWarning = true }
            } label: { Image(systemName: "plus").font(.title) }
        }
        .foregroundStyle(.white).padding(.horizontal, 28).padding(.vertical, 14)
    }

    private func libraryCard(_ game: LibraryGame) -> some View {
        ZStack(alignment: .topTrailing) {
            Button { play(game) } label: { GameCard(game: game, profile: library.profile(for: game), activity: library.activity(for: game)) }
                .buttonStyle(.plain)
                .contextMenu {
                    Button("Game settings", systemImage: "slider.horizontal.3") { selectedGame = game }
                    Button("Play", systemImage: "play.fill") { play(game) }
                    Button(library.activity(for: game).favorite ? "Remove favorite" : "Favorite", systemImage: "star") { library.toggleFavorite(game) }
                    if !game.isDesktop {
                        Button("Hide from library", systemImage: "eye.slash") { library.hide(game) }
                    }
                }
                .accessibilityHint("Play. Touch and hold for game settings.")
            Button { library.toggleFavorite(game) } label: {
                Image(systemName: library.activity(for: game).favorite ? "star.fill" : "star")
                    .foregroundStyle(library.activity(for: game).favorite ? Color.yellow : Color.white)
                    .padding(10).background(.black.opacity(0.7), in: Circle())
            }.buttonStyle(.plain).padding(16)
                .accessibilityLabel(library.activity(for: game).favorite ? "Remove \(game.title) from favorites" : "Favorite \(game.title)")
        }
    }

    private func play(_ game: LibraryGame) {
        guard !LinuxVMSession.shared.started, !LinuxVMSession.shared.installing else {
            library.error = "Restart My-pc before switching from Linux to Windows."
            return
        }
        if game.id == "steam-client" && !SteamInstaller.isInstalled { storesPresented = true }
        else if !game.isDesktop && game.executable == nil { selectedGame = game }
        else { launch(game, library.profile(for: game)) }
    }

    private func tab(_ title: String, icon: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Label(title, systemImage: icon).font(.headline).padding(.horizontal, 18).padding(.vertical, 14)
                .foregroundStyle(selected ? Color.blue : Color.white)
                .background(selected ? Color.black : Color.clear, in: Capsule())
        }.buttonStyle(.plain)
    }
}

private struct GameCard: View {
    let game: LibraryGame
    let profile: GameProfile
    let activity: GameActivity
    @State private var localImage: UIImage?
    private var coverURL: URL? {
        if let name = profile.customCover, name == URL(fileURLWithPath: name).lastPathComponent {
            return GameLibrary.documents.appendingPathComponent("Covers").appendingPathComponent(name)
        }
        return game.cover
    }
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Color.clear.aspectRatio(1, contentMode: .fit)
                .overlay {
                    if let localImage { Image(uiImage: localImage).resizable().scaledToFill() }
                    else if game.id == "pc" { Image("PCCover").resizable().scaledToFill() }
                    else if game.id == "steam-client" {
                        ZStack {
                            LinearGradient(colors: [.blue.opacity(0.5), Color(red: 0.02, green: 0.05, blue: 0.12)], startPoint: .topLeading, endPoint: .bottomTrailing)
                            Image("SteamLogo").resizable().scaledToFit().padding(20)
                        }
                    }
                    else if let steamID = game.steamID {
                        AsyncImage(url: URL(string: "https://cdn.akamai.steamstatic.com/steam/apps/\(steamID)/library_600x900_2x.jpg")) { phase in
                            if let image = phase.image { image.resizable().scaledToFill() } else { placeholder }
                        }
                    } else { placeholder }
                }
                .clipShape(RoundedRectangle(cornerRadius: 16))
            Text(game.title).font(.headline).lineLimit(1)
            Text(game.publisher).font(.subheadline).foregroundStyle(.secondary).lineLimit(1)
            if activity.seconds >= 60 {
                Text(activity.seconds >= 3600 ? String(format: "%.1f h played", activity.seconds / 3600) : "\(Int(activity.seconds / 60)) min played")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if let executable = game.executable {
                Text(executable.lastPathComponent).font(.caption).foregroundStyle(.secondary)
                    .lineLimit(1).truncationMode(.middle)
            }
        }
        .padding(12).padding(.bottom, 10)
        .background(Color(white: 0.12), in: RoundedRectangle(cornerRadius: 24))
        .overlay(RoundedRectangle(cornerRadius: 24).stroke(Color.white.opacity(0.16)))
        .shadow(color: .white.opacity(0.04), radius: 10)
        .task(id: coverURL) {
            localImage = nil
            guard let url = coverURL else { return }
            localImage = await Task.detached(priority: .utility) { Self.thumbnail(url) }.value
        }
    }
    private var placeholder: some View {
        ZStack {
            LinearGradient(colors: [.blue.opacity(0.5), .black], startPoint: .topLeading, endPoint: .bottomTrailing)
            Image(systemName: "gamecontroller.fill").font(.largeTitle).foregroundStyle(.white.opacity(0.8))
        }
    }
    static func thumbnail(_ url: URL) -> UIImage? {
        guard let source = CGImageSourceCreateWithURL(url as CFURL, nil),
              let image = CGImageSourceCreateThumbnailAtIndex(source, 0, [kCGImageSourceCreateThumbnailFromImageAlways: true, kCGImageSourceThumbnailMaxPixelSize: 640, kCGImageSourceCreateThumbnailWithTransform: true] as CFDictionary) else { return nil }
        return UIImage(cgImage: image)
    }
}

struct GameSettingsView: View {
    let game: LibraryGame
    @Environment(\.dismiss) private var dismiss
    @State private var profile = GameProfile()
    @State private var coverPicker = false
    @State private var error: String?
    @State private var selectedExecutable = ""

    init(game: LibraryGame) {
        self.game = game
        _profile = State(initialValue: GameLibrary.shared.profile(for: game))
        _selectedExecutable = State(initialValue: game.executable.map(GameLibrary.launcherPath) ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Game") {
                    Text(game.title).font(.headline)
                    if !game.isDesktop {
                        Picker("Launch executable", selection: $selectedExecutable) {
                            Text("Choose an EXE").tag("")
                            ForEach(game.candidates, id: \.path) { file in
                                let relative = GameLibrary.launcherPath(file)
                                Text(relative).tag(relative)
                            }
                        }
                        Text("One card per game folder. Select the game's launcher, not an installer or utility. Supporting data files are kept on disk.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    if let executable = game.executable { Text(executable.lastPathComponent).font(.caption) }
                    Button("Choose cover artwork") { coverPicker = true }
                    Button("Reset cover") { profile.customCover = nil }
                    if !game.isDesktop { TextField("Launch arguments", text: $profile.arguments) }
                }
                Section("Compatibility") {
                    if game.id.hasPrefix("steam:") {
                        Picker("Launch using", selection: Binding<String>(
                            get: { profile.launchThroughSteam.map { $0 ? "steam" : "direct" } ?? "automatic" },
                            set: { profile.launchThroughSteam = $0 == "automatic" ? nil : $0 == "steam" })) {
                            Text("Automatic").tag("automatic")
                            Text("Steam client").tag("steam")
                            Text("Direct EXE").tag("direct")
                        }
                        Text("Automatic uses Steam for games with a matching installed Steam manifest, so Steam can handle login and game startup. Otherwise it uses the selected EXE. Steam chooses its configured game launcher; set arguments in Steam → Properties → Launch Options.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    Toggle("Enable bundled ARM64 Visual C++", isOn: $profile.visualCppARM64)
                    Text("Installs the bundled, Microsoft-signed ARM64 DLLs and their verified version information for this session—no installer is launched. Experimental: some games remain incompatible. The default Wine/x64 exception handlers stay unchanged. Disable this option and restart to restore the default runtime.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                Section("Per-game settings") {
                    Toggle("Use custom settings", isOn: $profile.customSettings)
                    Text("Otherwise this game uses global settings. Changes apply on the next fresh app session; restart before switching games.").font(.caption).foregroundStyle(.secondary)
                }
                Group {
                    Section("Graphics") {
                        Picker("Resolution", selection: $profile.resolution) {
                            ForEach(EmulatorSettings.resolutions, id: \.self) { Text($0).tag($0) }
                        }
                        Toggle("Show FPS", isOn: $profile.showFPS)
                        Picker("Presentation pacing", selection: $profile.presentationMode) {
                            Text("60 FPS limit").tag(Int32(1))
                            Text("Display maximum").tag(Int32(0))
                            Text("Uncapped / frame skipping").tag(Int32(2))
                        }
                    }
                    Section("Controllers") {
                        Picker("Game input", selection: $profile.controllerMode) {
                            Text("Xbox-compatible (XInput)").tag("xinput")
                            Text("Keyboard & mouse").tag("keyboard")
                        }
                        LabeledContent("Stick dead zone", value: "\(Int(profile.deadZone * 100))%")
                        Slider(value: $profile.deadZone, in: 0...0.5, step: 0.01)
                        LabeledContent("Mouse speed", value: String(format: "%.1f", profile.mouseSpeed))
                        Slider(value: $profile.mouseSpeed, in: 1...20)
                        NavigationLink("Connected controllers & test") { ControllerTestView() }
                    }
                    Section("Touch & diagnostics") {
                        Toggle("Relative mouse", isOn: $profile.relativeMouse)
                        LabeledContent("Pointer sensitivity", value: String(format: "%.2f", profile.pointerSensitivity))
                        Slider(value: $profile.pointerSensitivity, in: 0.1...8)
                        LabeledContent("Mouse-look sensitivity", value: String(format: "%.2f", profile.mouseLookSensitivity))
                        Slider(value: $profile.mouseLookSensitivity, in: 0.1...8)
                        Toggle("Keep screen awake", isOn: $profile.keepAwake)
                        Toggle("Verbose diagnostics", isOn: $profile.diagnostics)
                    }
                }.disabled(!profile.customSettings)
            }
            .navigationTitle("Game Settings").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        do {
                            if !game.isDesktop { try GameLibrary.shared.selectExecutable(selectedExecutable, for: game) }
                            GameLibrary.shared.save(profile, for: game)
                            dismiss()
                        } catch { self.error = error.localizedDescription }
                    }
                }
            }
        }
        .fileImporter(isPresented: $coverPicker, allowedContentTypes: [.image]) { result in
            do {
                let source = try result.get()
                let access = source.startAccessingSecurityScopedResource()
                defer { if access { source.stopAccessingSecurityScopedResource() } }
                guard let image = GameCard.thumbnail(source), let data = image.pngData() else { throw LibraryFailure.invalid("Could not read this image.") }
                let folder = GameLibrary.documents.appendingPathComponent("Covers", isDirectory: true)
                try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                let name = UUID().uuidString + ".png"
                try data.write(to: folder.appendingPathComponent(name), options: .atomic)
                profile.customCover = name
            } catch { self.error = error.localizedDescription }
        }
        .alert("Cover artwork", isPresented: Binding(get: { error != nil }, set: { if !$0 { error = nil } })) {
            Button("OK", role: .cancel) { error = nil }
        } message: { Text(error ?? "") }
    }
}

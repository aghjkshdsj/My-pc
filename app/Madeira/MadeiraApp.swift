import SwiftUI

@main
struct MadeiraApp: App {
    @Environment(\.scenePhase) private var scenePhase

    init() {
        _ = CrashRecovery.shared
        _ = SessionDiagnostics.shared
        do { try RuntimeSupport.restoreRegistryIfNeeded() }
        catch { GameLibrary.shared.error = "Could not restore runtime settings: \(error.localizedDescription)" }
    }

    var body: some Scene {
        WindowGroup {
            AccountRootView()
                .onAppear { CrashRecovery.shared.record(foreground: true) }
                .onChange(of: scenePhase) { phase in
                    if phase == .active { CrashRecovery.shared.record(foreground: true) }
                    if phase == .background { CrashRecovery.shared.record(foreground: false) }
                }
        }
    }
}

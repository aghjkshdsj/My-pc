import SwiftUI

@main struct InterpreterApp: App {
    @State private var showingSteam = false
    var body: some Scene {
        WindowGroup {
            NavigationStack {
                List {
                    Section("Apps") {
                        Button { showingSteam = true } label: {
                            Label {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text("Steam ARM64")
                                    Text("Linux interpreter · No JIT required").font(.caption).foregroundStyle(.secondary)
                                }
                            } icon: { Image(systemName: "desktopcomputer") }
                        }
                    }
                    Section {
                        Text("Development preview. Steam startup and performance in this interpreter need device testing. Setup requires approximately 13 GB free.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
                .navigationTitle("Library")
                .fullScreenCover(isPresented: $showingSteam) { LinuxVMView() }
            }
            .preferredColorScheme(.dark)
        }
    }
}

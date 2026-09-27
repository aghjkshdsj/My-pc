import SwiftUI
import UniformTypeIdentifiers

struct LinuxVMView: View {
    @ObservedObject private var session = LinuxVMSession.shared
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var importing = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 12) {
                if let image = session.image {
                    GeometryReader { geometry in
                        let ratio = min(geometry.size.width / CGFloat(image.width), geometry.size.height / CGFloat(image.height))
                        let size = CGSize(width: CGFloat(image.width) * ratio, height: CGFloat(image.height) * ratio)
                        Image(decorative: image, scale: 1).resizable().interpolation(.none)
                            .frame(width: size.width, height: size.height)
                            .contentShape(Rectangle())
                            .gesture(DragGesture(minimumDistance: 0)
                                .onChanged { value in session.pointer(x: value.location.x / size.width, y: value.location.y / size.height, down: true) }
                                .onEnded { value in session.pointer(x: value.location.x / size.width, y: value.location.y / size.height, down: false) })
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    }
                } else {
                    Image(systemName: "desktopcomputer").font(.system(size: 64)).foregroundStyle(.secondary)
                    Text("ARM64 Linux preview").font(.title2.bold())
                    Text("This development stage tests Linux boot and display. Steam login and gaming are not yet validated.")
                        .foregroundStyle(.secondary).multilineTextAlignment(.center)
                    Spacer()
                }
                Text(session.status).font(.footnote).textSelection(.enabled)
                if session.installing { ProgressView() }
                HStack {
                    if !session.installed {
                        Button("Import runtime folder") { importing = true }.disabled(session.installing)
                    } else if !session.started {
                        Button("Enable JIT") {
                            StikJITHelper.enableJIT { success in
                                if !success { session.error = "StikDebug could not enable JIT. Check its connection and retry." }
                            }
                        }
                        Button("Boot Linux") { session.start() }.buttonStyle(.borderedProminent)
                    }
                    if session.running { Button("Shut down") { session.shutdown() }.disabled(!session.connected) }
                }
            }
            .padding().background(.black).foregroundStyle(.white)
            .navigationTitle("Linux ARM64")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() }.disabled(session.running || session.installing) } }
            .fileImporter(isPresented: $importing, allowedContentTypes: [.folder]) { result in
                switch result {
                case .success(let folder): session.importRuntime(folder)
                case .failure(let error): session.error = error.localizedDescription
                }
            }
            .alert("Linux ARM64", isPresented: Binding(get: { session.error != nil }, set: { if !$0 { session.error = nil } })) {
                Button("OK") { session.error = nil }
            } message: { Text(session.error ?? "") }
            .onChange(of: scenePhase) { _, phase in session.setBackground(phase != .active) }
        }
        .interactiveDismissDisabled(session.running || session.installing)
        .preferredColorScheme(.dark)
    }
}

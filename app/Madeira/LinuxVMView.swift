import SwiftUI
import UniformTypeIdentifiers
import UIKit

private struct LinuxKeyboard: UIViewRepresentable {
    var active: Bool
    var text: (String) -> Void
    var backspace: () -> Void
    final class Input: UIView, UIKeyInput {
        var text: (String) -> Void = { _ in }
        var backspace: () -> Void = {}
        var hasText: Bool { true }
        override var canBecomeFirstResponder: Bool { true }
        var keyboardType: UIKeyboardType = .asciiCapable
        var autocorrectionType: UITextAutocorrectionType = .no
        var autocapitalizationType: UITextAutocapitalizationType = .none
        var smartQuotesType: UITextSmartQuotesType = .no
        var smartDashesType: UITextSmartDashesType = .no
        func insertText(_ text: String) { self.text(text) }
        func deleteBackward() { backspace() }
    }
    func makeUIView(context: Context) -> Input { Input() }
    func updateUIView(_ view: Input, context: Context) {
        view.text = text; view.backspace = backspace
        DispatchQueue.main.async {
            if active && !view.isFirstResponder { view.becomeFirstResponder() }
            else if !active && view.isFirstResponder { view.resignFirstResponder() }
        }
    }
}

struct LinuxVMView: View {
    @ObservedObject private var session = LinuxVMSession.shared
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @State private var importing = false
    @State private var keyboard = false

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
                    Text("Steam ARM64 preview").font(.title2.bold())
                    Text("Set up Linux, enable JIT, then open Steam. The full ARM64 client downloads from Valve on its first launch. This experimental build still needs iPhone testing.")
                        .foregroundStyle(.secondary).multilineTextAlignment(.center)
                    Spacer()
                }
                Text(session.status).font(.footnote).textSelection(.enabled)
                if session.connected {
                    HStack {
                        Button { keyboard.toggle() } label: { Image(systemName: keyboard ? "keyboard.chevron.compact.down" : "keyboard") }.accessibilityLabel("Toggle keyboard")
                        Button("Esc") { session.press("esc") }
                        Button("Tab") { session.press("tab") }
                        Button("Enter") { session.press("ret") }
                        Button("↑") { session.press("up") }
                        Button("↓") { session.press("down") }
                    }.buttonStyle(.bordered)
                }
                if session.installing { ProgressView(value: session.installProgress) }
                HStack {
                    if !session.installed {
                        if LinuxVMSession.bundledRuntime != nil {
                            Button("Set up Steam ARM64") { session.installBundledRuntime() }
                                .buttonStyle(.borderedProminent).disabled(session.installing)
                        }
                        Button("Import runtime folder") { importing = true }.disabled(session.installing)
                    } else if !session.started {
                        Button("Enable JIT") {
                            StikJITHelper.enableJIT { success in
                                if !success { session.error = "StikDebug could not enable JIT. Check its connection and retry." }
                            }
                        }
                        Button("Open Steam") { session.start() }.buttonStyle(.borderedProminent)
                    }
                    if session.running { Button("Shut down") { session.shutdown() }.disabled(!session.connected) }
                }
            }
            .padding().background(.black).foregroundStyle(.white)
            .background(LinuxKeyboard(active: keyboard && session.connected, text: session.type, backspace: { session.press("backspace") }).frame(width: 1, height: 1))
            .navigationTitle("Steam ARM64")
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

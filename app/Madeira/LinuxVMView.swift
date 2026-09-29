import SwiftUI
import UniformTypeIdentifiers
import UIKit

private struct LinuxMouseCursor: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let points: [CGPoint] = [CGPoint(x: 0, y: 0), CGPoint(x: 0, y: 0.8),
            CGPoint(x: 0.26, y: 0.61), CGPoint(x: 0.49, y: 1),
            CGPoint(x: 0.69, y: 0.88), CGPoint(x: 0.47, y: 0.51),
            CGPoint(x: 0.82, y: 0.51)]
        path.addLines(points.map { CGPoint(x: $0.x * rect.width, y: $0.y * rect.height) })
        path.closeSubpath()
        return path
    }
}

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
    @State private var zoomed = false
    @State private var trackpad = false
    @State private var mousePoint = CGPoint(x: 0.5, y: 0.5)
    @State private var gestureOrigin: CGPoint?
    @State private var dragging = false
    @State private var showPerformance = true
    @State private var performanceHelp = false
    @State private var cpuSettings = false

    var body: some View {
        NavigationStack {
            Group {
                if let image = session.image {
                    desktop(image)
                } else {
                    VStack(spacing: 12) {
                        Image(systemName: "desktopcomputer").font(.system(size: 64)).foregroundStyle(.secondary)
                        Text("Steam ARM64 preview").font(.title2.bold())
                        Text(LinuxExecutionMode.setupHelp)
                            .foregroundStyle(.secondary).multilineTextAlignment(.center)
                        Spacer()
                        cpuPicker
                        Text(session.status).font(.footnote).textSelection(.enabled)
                        if session.installing { ProgressView(value: session.installProgress) }
                        HStack {
                            if !session.installed {
                                if LinuxVMSession.bundledRuntime != nil {
                                    Button("Set up Steam ARM64") { session.installBundledRuntime() }
                                        .buttonStyle(.borderedProminent).disabled(session.installing)
                                }
                                Button("Import runtime folder") { importing = true }.disabled(session.installing)
                            } else if !session.started {
                                #if !MYPC_INTERPRETER
                                Button("Enable JIT") {
                                    StikJITHelper.enableJIT { success in
                                        if !success { session.error = "StikDebug could not enable JIT. Check its connection and retry." }
                                    }
                                }
                                #endif
                                Button("Open Steam") { session.start() }.buttonStyle(.borderedProminent)
                            }
                            if session.running { Button("Shut down") { session.shutdown() }.disabled(!session.connected) }
                        }
                    }.padding()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(.black).foregroundStyle(.white)
            .background(LinuxKeyboard(active: keyboard && session.connected, text: session.type, backspace: { session.press("backspace") }).frame(width: 1, height: 1))
            .navigationTitle("Steam ARM64")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar(session.image == nil ? .visible : .hidden, for: .navigationBar)
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
            .onChange(of: scenePhase) { _, phase in
                if phase != .active { releaseMouse() }
                session.setBackground(phase != .active)
            }
            .onChange(of: trackpad) { _, _ in releaseMouse() }
            .sheet(isPresented: $performanceHelp) {
                NavigationStack {
                    List {
                        Text("CPU is this app's total use across its threads, including Linux emulation. 100% means one fully busy core; it can exceed 100%. It is not the guest's CPU percentage.")
                        Text("RAM is this app's physical memory footprint, including QEMU and the display. Linux has \(session.guestMemoryMiB) MiB allocated and \(session.guestCPUCount) virtual CPUs. Allocation is not memory usage.")
                        Text("This session has \(session.guestCPUCount) virtual CPU cores. iOS reports \(session.hostCPUCount) available host cores. CPU core settings apply at startup; iOS controls scheduling, power and thermal limits. More cores do not guarantee a faster interface.")
                        Text("Display FPS counts new guest frames shown each second, up to 30. An idle desktop can show 0 FPS. This is not a game's internal FPS.")
                        Text("Steam currently uses CPU software rendering. GPU utilization is unavailable in this build; no GPU percentage is estimated.")
                        Text("Device thermal state: \(session.thermalStatus). iOS decides CPU scheduling and thermal limits.")
                    }
                    .navigationTitle("Performance")
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { performanceHelp = false } } }
                }.presentationDetents([.medium, .large])
            }
            .sheet(isPresented: $cpuSettings) {
                NavigationStack {
                    Form {
                        cpuPicker
                        Text("All available cores is the default. More virtual CPUs can help parallel work, but also add overhead. iOS controls scheduling and thermal limits.")
                        Text("Choose before starting Linux. After a session, shut down Linux and restart My-pc to change this setting. Your installed disk is preserved.")
                    }
                    .navigationTitle("CPU cores")
                    .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { cpuSettings = false } } }
                }.presentationDetents([.medium])
            }
        }
        .interactiveDismissDisabled(session.running || session.installing)
        .preferredColorScheme(.dark)
    }

    private func desktop(_ image: CGImage) -> some View {
        GeometryReader { geometry in
            let scale = min(geometry.size.width / CGFloat(image.width), geometry.size.height / CGFloat(image.height)) * (zoomed ? 1.5 : 1)
            let size = CGSize(width: CGFloat(image.width) * scale, height: CGFloat(image.height) * scale)
            let panX = zoomed ? min(max(0, (size.width - geometry.size.width) / 2), max(-max(0, (size.width - geometry.size.width) / 2), (0.5 - mousePoint.x) * size.width)) : 0
            let panY = zoomed ? min(max(0, (size.height - geometry.size.height) / 2), max(-max(0, (size.height - geometry.size.height) / 2), (0.5 - mousePoint.y) * size.height)) : 0
            ZStack(alignment: .topLeading) {
                Image(decorative: image, scale: 1).resizable().interpolation(.none)
                LinuxMouseCursor().fill(.white)
                    .overlay(LinuxMouseCursor().stroke(.black, lineWidth: 1.5))
                    .frame(width: 18, height: 24)
                    .offset(x: mousePoint.x * size.width, y: mousePoint.y * size.height)
                    .shadow(color: .black.opacity(0.7), radius: 2)
                    .allowsHitTesting(false).accessibilityHidden(true)
            }
                .frame(width: size.width, height: size.height)
                .contentShape(Rectangle())
                .gesture(DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        if trackpad {
                            if gestureOrigin == nil { gestureOrigin = mousePoint }
                            let origin = gestureOrigin ?? mousePoint
                            moveMouse(x: origin.x + value.translation.width / size.width,
                                      y: origin.y + value.translation.height / size.height, down: dragging)
                        } else {
                            moveMouse(x: value.location.x / size.width, y: value.location.y / size.height, down: true)
                        }
                    }
                    .onEnded { value in
                        if trackpad {
                            if !dragging && hypot(value.translation.width, value.translation.height) < 8 {
                                session.click(x: mousePoint.x, y: mousePoint.y)
                            }
                        } else {
                            moveMouse(x: value.location.x / size.width, y: value.location.y / size.height, down: false)
                        }
                        gestureOrigin = nil
                    })
                .onContinuousHover { phase in
                    guard !trackpad else { return }
                    if case .active(let location) = phase {
                        moveMouse(x: location.x / size.width, y: location.y / size.height, down: false)
                    }
                }
                .offset(x: panX, y: panY)
                .frame(width: geometry.size.width, height: geometry.size.height)
                .clipped()
        }
        .overlay(alignment: .topLeading) {
            if showPerformance {
                Button { performanceHelp = true } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("CPU \(session.cpuPercent.map { String(format: "%.0f%%", $0) } ?? "—") · RAM \(session.memoryMiB.map { String(format: "%.0f MiB", $0) } ?? "—")")
                        Text(String(format: "Display %.1f FPS · GPU: software", session.displayFPS))
                        Text("VM \(session.guestCPUCount) cores")
                    }
                    .font(.system(size: 11, design: .monospaced)).monospacedDigit()
                    .foregroundStyle(.white).padding(6)
                    .background(.black.opacity(0.8), in: RoundedRectangle(cornerRadius: 6))
                }.buttonStyle(.plain).padding(6)
                .accessibilityLabel("Performance monitor. Tap for metric definitions")
            }
        }
        .safeAreaInset(edge: .bottom, spacing: 0) {
            HStack(spacing: 8) {
                Button { keyboard.toggle() } label: { Image(systemName: keyboard ? "keyboard.chevron.compact.down" : "keyboard") }
                    .accessibilityLabel("Toggle keyboard")
                    .disabled(!session.connected)
                Button("Esc") { session.press("esc") }.disabled(!session.connected)
                Button("Tab") { session.press("tab") }.disabled(!session.connected)
                Button("Enter") { session.press("ret") }.disabled(!session.connected)
                Spacer(minLength: 0)
                Button {
                    zoomed.toggle()
                    if zoomed { trackpad = true }
                } label: { Image(systemName: zoomed ? "arrow.down.right.and.arrow.up.left" : "plus.magnifyingglass") }
                    .accessibilityLabel(zoomed ? "Fit desktop to screen" : "Enlarge desktop")
                Menu {
                    Text(session.status)
                    Button("CPU cores (\(session.guestCPUCount))") { cpuSettings = true }
                    Toggle("Touch as trackpad", isOn: $trackpad)
                    if trackpad {
                        Button(dragging ? "Release mouse drag" : "Hold mouse for dragging") {
                            dragging.toggle()
                            session.pointer(x: mousePoint.x, y: mousePoint.y, down: dragging)
                        }.disabled(!session.connected)
                    }
                    Button("Click") { session.click(x: mousePoint.x, y: mousePoint.y) }.disabled(!session.connected || dragging)
                    Button("Right-click") { session.click(x: mousePoint.x, y: mousePoint.y, button: .right) }.disabled(!session.connected || dragging)
                    Button("Scroll up") { session.click(x: mousePoint.x, y: mousePoint.y, button: .wheelUp) }.disabled(!session.connected || dragging)
                    Button("Scroll down") { session.click(x: mousePoint.x, y: mousePoint.y, button: .wheelDown) }.disabled(!session.connected || dragging)
                    Toggle("Performance monitor", isOn: $showPerformance)
                    Button("Performance details") { performanceHelp = true }
                    Button("Up arrow") { session.press("up") }.disabled(!session.connected)
                    Button("Down arrow") { session.press("down") }.disabled(!session.connected)
                    Button("Shut down Linux", role: .destructive) { session.shutdown() }.disabled(!session.running || !session.connected)
                    Button("Close") { dismiss() }.disabled(session.running || session.installing)
                } label: { Image(systemName: "ellipsis") }
                .accessibilityLabel("Session options")
            }
            .font(.footnote).buttonStyle(.bordered)
            .padding(.horizontal, 8).padding(.vertical, 4).background(.black)
        }
    }

    private var cpuPicker: some View {
        Picker("CPU cores", selection: Binding(get: { session.cpuSelection }, set: { session.selectCPUCount($0) })) {
            Text("All available (\(session.hostCPUCount))").tag(0)
            ForEach(1...session.hostCPUCount, id: \.self) { count in
                Text("\(count) \(count == 1 ? "core" : "cores")").tag(count)
            }
        }.disabled(session.started || session.installing)
    }

    private func moveMouse(x: CGFloat, y: CGFloat, down: Bool) {
        mousePoint = CGPoint(x: x.isFinite ? min(1, max(0, x)) : 0,
                             y: y.isFinite ? min(1, max(0, y)) : 0)
        session.pointer(x: mousePoint.x, y: mousePoint.y, down: down)
    }

    private func releaseMouse() {
        session.pointer(x: mousePoint.x, y: mousePoint.y, down: false)
        dragging = false; gestureOrigin = nil
    }
}

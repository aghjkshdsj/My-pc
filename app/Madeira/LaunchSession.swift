import SwiftUI
import UIKit

final class LaunchSession: ObservableObject {
    static let shared = LaunchSession()
    @Published private(set) var stage: StartupStage = .requested
    @Published private(set) var active = false
    @Published private(set) var failure: String?
    @Published private(set) var title = "Something PC"
    @Published private(set) var elapsed = 0
    @Published private(set) var displayEarly = false
    private var started = Date()
    private var initialMetal: UInt64 = 0
    private var initialGDI: UInt64 = 0
    private var timer: Timer?
    var ready: Bool { active && (stage == .firstFrame || displayEarly) && failure == nil }

    func begin(_ game: LibraryGame) {
        PlaytimeRecorder.shared.begin(game.id)
        stage = .requested
        title = game.title
        failure = nil
        active = true
        displayEarly = false
        elapsed = 0
        started = Date()
        initialMetal = madeira_get_present_count()
        initialGDI = spc_gdi_present_count()
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 0.5, repeats: true) { [weak self] _ in self?.tick() }
        SessionDiagnostics.shared.event("Startup requested: \(game.title)")
    }

    func advance(_ value: StartupStage) {
        DispatchQueue.main.async {
            guard self.active, self.failure == nil, value.rawValue > self.stage.rawValue else { return }
            self.stage = value
            SessionDiagnostics.shared.event("Startup \(value.percent)%: \(value.title)")
        }
    }

    func fail(_ message: String) {
        DispatchQueue.main.async {
            guard self.active else { return }
            self.failure = message
            PlaytimeRecorder.shared.setVisible(false)
            self.timer?.invalidate()
            SessionDiagnostics.shared.event("Startup failed: \(message)")
        }
    }

    func showSession() { displayEarly = true }

    private func tick() {
        guard active, failure == nil else { return }
        elapsed = Int(Date().timeIntervalSince(started))
        guard stage == .processReady else { return }
        if madeira_get_present_count() > initialMetal || spc_gdi_present_count() > initialGDI {
            advance(.firstFrame)
            timer?.invalidate()
        }
    }
}

final class PlaytimeRecorder: NSObject {
    static let shared = PlaytimeRecorder()
    private var gameID: String?
    private var visible = false
    private var previous: TimeInterval?
    private var timer: Timer?

    private override init() {
        super.init()
        NotificationCenter.default.addObserver(self, selector: #selector(suspend), name: UIApplication.willResignActiveNotification, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(resume), name: UIApplication.didBecomeActiveNotification, object: nil)
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in self?.checkpoint() }
    }

    func begin(_ id: String) {
        checkpoint()
        gameID = id
        visible = false
        previous = nil
    }

    func setVisible(_ value: Bool) {
        checkpoint()
        visible = value
        resume()
    }

    @objc private func suspend() { checkpoint(); previous = nil }
    @objc private func resume() {
        previous = visible && UIApplication.shared.applicationState == .active && wine_process_is_running() != 0 ? ProcessInfo.processInfo.systemUptime : nil
    }

    private func checkpoint() {
        if let previous, let gameID {
            GameLibrary.shared.addPlaytime(max(0, min(30, ProcessInfo.processInfo.systemUptime - previous)), id: gameID)
        }
        resume()
    }
}

struct StartupView: View {
    @ObservedObject private var session = LaunchSession.shared
    let library: () -> Void
    let share: () -> Void
    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(red: 0.015, green: 0.045, blue: 0.1), .black], startPoint: .topLeading, endPoint: .bottomTrailing).ignoresSafeArea()
            GeometryReader { geometry in
              ScrollView {
               VStack(spacing: geometry.size.height < 500 ? 8 : 18) {
                Image("PCCover").resizable().scaledToFit()
                    .frame(width: geometry.size.height < 500 ? 52 : 96, height: geometry.size.height < 500 ? 52 : 96)
                    .clipShape(RoundedRectangle(cornerRadius: 22))
                Text(session.title).font(.title2.bold()).lineLimit(2)
                if let failure = session.failure {
                    Label("Couldn’t start this session", systemImage: "exclamationmark.triangle").font(.headline)
                    Text(failure).font(.callout).foregroundStyle(.secondary)
                } else {
                    Text("\(session.stage.percent)%").font(.system(size: 42, weight: .semibold, design: .rounded)).monospacedDigit()
                    ProgressView(value: Double(session.stage.percent), total: 100).tint(.cyan)
                    Text(session.stage.title).font(.headline)
                    Text("Startup milestones · \(session.elapsed)s\n100% means the first frame was rendered, not that the game's own loading is finished.")
                        .font(.caption).foregroundStyle(.secondary)
                    if session.elapsed > 45 {
                        Text("Still waiting on this step. Progress does not advance on a timer. JIT may require returning from StikDebug.")
                            .font(.caption).foregroundStyle(.orange)
                        if session.stage == .processReady { Button("Show session while waiting") { session.showSession() } }
                    }
                }
                HStack {
                    Button("Library", action: library)
                    Button("Share diagnostics", action: share)
                }.buttonStyle(.bordered)
                Text(session.failure == nil ? "Returning to Library does not terminate Windows startup." : "A fresh app launch may be required before trying again.")
                    .font(.caption2).foregroundStyle(.secondary)
               }
               .multilineTextAlignment(.center).frame(maxWidth: 460).padding(24)
               .frame(maxWidth: .infinity, minHeight: geometry.size.height)
              }
            }
        }.preferredColorScheme(.dark)
    }
}

private final class SessionMenuWindow: UIWindow {
    override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView? {
        let hit = super.hitTest(point, with: event)
        return hit == rootViewController?.view ? nil : hit
    }
}

private final class SessionMenuController: UIViewController {
    override var prefersStatusBarHidden: Bool { true }
}

enum SessionMenuHost {
    private static var window: SessionMenuWindow?
    private static var fpsController: UIHostingController<FPSOverlay>?
    static func show(_ visible: Bool) {
        if window == nil && visible {
            guard let scene = UIApplication.shared.connectedScenes.compactMap({ $0 as? UIWindowScene }).first(where: { $0.activationState == .foregroundActive }) else { return }
            let host = SessionMenuWindow(windowScene: scene)
            host.windowLevel = .normal + 102
            host.backgroundColor = .clear
            let controller = SessionMenuController()
            controller.view.backgroundColor = .clear
            let fps = UIHostingController(rootView: FPSOverlay(compact: true))
            fps.view.backgroundColor = .clear
            fps.view.translatesAutoresizingMaskIntoConstraints = false
            controller.addChild(fps)
            controller.view.addSubview(fps.view)
            fps.didMove(toParent: controller)
            fpsController = fps
            let button = UIButton(type: .system)
            button.setImage(UIImage(systemName: "ellipsis.circle.fill"), for: .normal)
            button.tintColor = .white
            button.backgroundColor = UIColor.black.withAlphaComponent(0.55)
            button.layer.cornerRadius = 23
            button.translatesAutoresizingMaskIntoConstraints = false
            button.accessibilityLabel = "Session menu"
            button.showsMenuAsPrimaryAction = true
            button.menu = UIMenu(children: [
                UIAction(title: "Library & Settings", image: UIImage(systemName: "square.grid.2x2")) { _ in NotificationCenter.default.post(name: Notification.Name("somethingpc.openSettings"), object: nil) },
                UIAction(title: "Keyboard", image: UIImage(systemName: "keyboard")) { _ in MetalBackedView.toggleKeyboard() },
                UIAction(title: "Escape") { _ in winios_post_key(0x1b, 1); winios_post_key(0x1b, 0) },
                UIAction(title: "Share diagnostics", image: UIImage(systemName: "square.and.arrow.up")) { _ in NotificationCenter.default.post(name: Notification.Name("somethingpc.shareDiagnostics"), object: nil) }
            ])
            controller.view.addSubview(button)
            NSLayoutConstraint.activate([
                fps.view.widthAnchor.constraint(equalToConstant: 90), fps.view.heightAnchor.constraint(equalToConstant: 72),
                fps.view.leadingAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.leadingAnchor, constant: 8),
                fps.view.topAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.topAnchor, constant: 8),
                button.widthAnchor.constraint(equalToConstant: 46), button.heightAnchor.constraint(equalToConstant: 46),
                button.trailingAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.trailingAnchor, constant: -12),
                button.topAnchor.constraint(equalTo: controller.view.safeAreaLayoutGuide.topAnchor, constant: 8)
            ])
            host.rootViewController = controller
            window = host
        }
        fpsController?.view.isHidden = !EmulatorSettings.shared.showFPS
        window?.isHidden = !visible
    }
}

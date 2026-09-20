import SwiftUI
import GameController
import UIKit

final class EmulatorSettings: ObservableObject {
    static let shared = EmulatorSettings()
    static let resolutions = ["960x540", "800x600", "1024x768", "1280x720", "1600x900", "1920x1080"]
    @Published var resolution = "960x540" { didSet { save() } }
    @Published var showFPS = true { didSet { save() } }
    @Published var presentationMode: Int32 = 1 {
        didSet {
            madeira_set_vsync_locked(presentationMode)
            ProMotionIntent.shared.setActive(presentationMode != 1)
            save()
        }
    }
    @Published var keepAwake = true { didSet { UIApplication.shared.isIdleTimerDisabled = keepAwake; save() } }
    @Published var controllerMode = "xinput" { didSet { save() } }
    @Published var deadZone = 0.15 { didSet { save() } }
    @Published var mouseSpeed = 8.0 { didSet { save() } }
    private var loading = true
    private var sessionOriginal: GameProfile?
    private let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
        .appendingPathComponent("somethingpc-settings.json")

    var width: Int { Int(resolution.split(separator: "x")[0]) ?? 960 }
    var height: Int { Int(resolution.split(separator: "x").last ?? "540") ?? 540 }

    static var activeSize: CGSize {
        let settings = shared
        let width = getenv("MADEIRA_SCREEN_W").flatMap { Int(String(cString: $0)) } ?? settings.width
        let height = getenv("MADEIRA_SCREEN_H").flatMap { Int(String(cString: $0)) } ?? settings.height
        return CGSize(width: max(width, 1), height: max(height, 1))
    }

    private init() {
        if let data = try? Data(contentsOf: url),
           let values = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any] {
            if let saved = values["resolution"] as? String, Self.resolutions.contains(saved) { resolution = saved }
            showFPS = values["showFPS"] as? Bool ?? true
            presentationMode = Int32(min(2, max(0, values["presentationMode"] as? Int ?? 1)))
            keepAwake = values["keepAwake"] as? Bool ?? true
            controllerMode = values["controllerMode"] as? String == "keyboard" ? "keyboard" : "xinput"
            deadZone = min(max(values["deadZone"] as? Double ?? 0.15, 0), 0.5)
            mouseSpeed = min(max(values["mouseSpeed"] as? Double ?? 8, 1), 20)
        }
        loading = false
        madeira_set_vsync_locked(presentationMode)
        ProMotionIntent.shared.setActive(presentationMode != 1)
        UIApplication.shared.isIdleTimerDisabled = keepAwake
    }

    func applyResolution() {
        setenv("MADEIRA_SCREEN_W", String(width), 1)
        setenv("MADEIRA_SCREEN_H", String(height), 1)
    }

    func beginSession(_ profile: GameProfile) {
        endSession()
        var original = GameProfile()
        original.customSettings = true
        original.resolution = resolution
        original.showFPS = showFPS
        original.presentationMode = presentationMode
        original.keepAwake = keepAwake
        original.controllerMode = controllerMode
        original.deadZone = deadZone
        original.mouseSpeed = mouseSpeed
        original.relativeMouse = InputSettings.shared.relative
        original.pointerSensitivity = InputSettings.shared.sensAbs
        original.mouseLookSensitivity = InputSettings.shared.sensRel
        original.diagnostics = InputSettings.shared.diagnostics
        sessionOriginal = original
        loading = true
        applySessionValues(profile.customSettings ? profile : original)
    }

    func endSession() {
        guard let original = sessionOriginal else { return }
        applySessionValues(original)
        sessionOriginal = nil
        loading = false
        InputSettings.shared.finishSession()
    }

    private func applySessionValues(_ profile: GameProfile) {
        resolution = Self.resolutions.contains(profile.resolution) ? profile.resolution : "960x540"
        showFPS = profile.showFPS
        presentationMode = min(2, max(0, profile.presentationMode))
        keepAwake = profile.keepAwake
        controllerMode = profile.controllerMode == "keyboard" ? "keyboard" : "xinput"
        deadZone = min(0.5, max(0, profile.deadZone))
        mouseSpeed = min(20, max(1, profile.mouseSpeed))
        InputSettings.shared.applySession(profile)
    }

    private func save() {
        guard !loading else { return }
        let values: [String: Any] = ["resolution": resolution, "showFPS": showFPS,
            "presentationMode": Int(presentationMode), "keepAwake": keepAwake, "controllerMode": controllerMode,
            "deadZone": deadZone, "mouseSpeed": mouseSpeed]
        do {
            let data = try JSONSerialization.data(withJSONObject: values)
            try data.write(to: url, options: .atomic)
        } catch {
            LogStore.shared.log("Could not save settings: \(error.localizedDescription)", level: .error)
        }
    }
}

struct ControllerDevice: Identifiable {
    let id: Int
    let name: String
    let buttons: UInt16
    let leftTrigger: Float
    let rightTrigger: Float
    let leftX: Float
    let leftY: Float
    let rightX: Float
    let rightY: Float
    let battery: String
}

@MainActor
final class GameControllerManager: NSObject, ObservableObject {
    static let shared = GameControllerManager()
    static let buttonMasks: [(String, UInt16)] = [
        ("A", 0x1000), ("B", 0x2000), ("X", 0x4000), ("Y", 0x8000),
        ("LB", 0x100), ("RB", 0x200), ("D↑", 1), ("D↓", 2), ("D←", 4), ("D→", 8),
        ("Menu", 0x10), ("View", 0x20), ("L3", 0x40), ("R3", 0x80), ("Guide", 0x400)]
    @Published private(set) var devices: [ControllerDevice] = []
    @Published var suspended = false { didSet { if suspended { releaseAll() } } }
    private var slots: [GCController?] = Array(repeating: nil, count: 4)
    private var timer: Timer?
    private var frame = 0
    private var heldKeys: Set<Int32> = []
    private var mouseButtons: UInt32 = 0
    private var virtualButtons: Set<String> = []

    override private init() {
        super.init()
        NotificationCenter.default.addObserver(self, selector: #selector(refresh),
            name: .GCControllerDidConnect, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(refresh),
            name: .GCControllerDidDisconnect, object: nil)
        NotificationCenter.default.addObserver(self, selector: #selector(background),
            name: UIApplication.willResignActiveNotification, object: nil)
        refresh()
        let timer = Timer(timeInterval: 1.0 / 60.0, target: self, selector: #selector(tick), userInfo: nil, repeats: true)
        RunLoop.main.add(timer, forMode: .common)
        self.timer = timer
    }

    @objc private func refresh() {
        let available = GCController.controllers().filter { $0.extendedGamepad != nil }
        for index in slots.indices {
            if let controller = slots[index], !available.contains(where: { $0 === controller }) {
                slots[index] = nil
                clearSlot(index)
            }
        }
        for controller in available where !slots.contains(where: { $0 === controller }) {
            guard let index = slots.firstIndex(where: { $0 == nil }) else { break }
            slots[index] = controller
            controller.playerIndex = GCControllerPlayerIndex(rawValue: index) ?? .indexUnset
        }
        tick()
    }

    @objc private func background() { releaseAll() }

    func setVirtualButton(_ name: String, down: Bool) {
        if down { virtualButtons.insert(name) } else { virtualButtons.remove(name) }
        tick()
    }

    private func clearSlot(_ index: Int) {
        spc_controller_update(Int32(index), 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    }

    private func releaseAll() {
        for index in slots.indices { clearSlot(index) }
        for key in heldKeys { winios_post_key(key, 0) }
        heldKeys.removeAll()
        if mouseButtons & 1 != 0 { winios_pointer(0, 0, 0x4, 0) }
        if mouseButtons & 2 != 0 { winios_pointer(0, 0, 0x10, 0) }
        mouseButtons = 0
        virtualButtons.removeAll()
    }

    @objc private func tick() {
        frame += 1
        let settings = EmulatorSettings.shared
        var snapshots: [ControllerDevice] = []
        var desiredKeys: Set<Int32> = []
        var desiredMouse: UInt32 = 0
        let active = !suspended && UIApplication.shared.applicationState == .active
        for index in slots.indices {
            let controller = slots[index]
            let pad = controller?.extendedGamepad
            var buttons: UInt16 = 0
            if let pad {
                let values: [(GCControllerButtonInput?, UInt16)] = [
                    (pad.buttonA, 0x1000), (pad.buttonB, 0x2000), (pad.buttonX, 0x4000), (pad.buttonY, 0x8000),
                    (pad.leftShoulder, 0x100), (pad.rightShoulder, 0x200), (pad.dpad.up, 1), (pad.dpad.down, 2),
                    (pad.dpad.left, 4), (pad.dpad.right, 8), (pad.buttonMenu, 0x10), (pad.buttonOptions, 0x20),
                    (pad.leftThumbstickButton, 0x40), (pad.rightThumbstickButton, 0x80), (pad.buttonHome, 0x400)]
                for (button, mask) in values where button?.isPressed == true { buttons |= mask }
            }
            if index == 0 {
                for (name, mask) in Self.buttonMasks where virtualButtons.contains(name) { buttons |= mask }
            }
            let leftTrigger = max(pad?.leftTrigger.value ?? 0, index == 0 && virtualButtons.contains("LT") ? 1 : 0)
            let rightTrigger = max(pad?.rightTrigger.value ?? 0, index == 0 && virtualButtons.contains("RT") ? 1 : 0)
            let leftX = pad?.leftThumbstick.xAxis.value ?? 0
            let leftY = pad?.leftThumbstick.yAxis.value ?? 0
            let rightX = pad?.rightThumbstick.xAxis.value ?? 0
            let rightY = pad?.rightThumbstick.yAxis.value ?? 0
            let virtualConfigured = TouchControlsModel.shared.visible && TouchControlsModel.shared.controls.contains {
                if case .pad = $0.action { return true }
                return false
            }
            let connected = controller != nil || (index == 0 && virtualConfigured)
            var batteryType: UInt8 = 255
            var batteryLevel: UInt8 = 0
            var batteryText = "Battery unavailable"
            if let battery = controller?.battery, battery.batteryLevel >= 0 {
                batteryType = 2
                batteryLevel = UInt8(min(3, max(0, Int((battery.batteryLevel * 3).rounded()))))
                batteryText = "\(Int((battery.batteryLevel * 100).rounded()))% battery"
            }
            if let controller {
                snapshots.append(ControllerDevice(id: index, name: controller.vendorName ?? "Game controller",
                    buttons: buttons, leftTrigger: leftTrigger, rightTrigger: rightTrigger,
                    leftX: leftX, leftY: leftY, rightX: rightX, rightY: rightY, battery: batteryText))
            }
            func axis(_ value: Float) -> Int16 {
                let threshold = Float(settings.deadZone)
                guard abs(value) > threshold else { return 0 }
                let scaled = (abs(value) - threshold) / (1 - threshold)
                return Int16(max(-32767, min(32767, (value < 0 ? -scaled : scaled) * 32767)))
            }
            if active && connected && settings.controllerMode == "xinput" {
                spc_controller_update(Int32(index), 1, buttons,
                    UInt8(min(255, max(0, leftTrigger * 255))), UInt8(min(255, max(0, rightTrigger * 255))),
                    axis(leftX), axis(leftY), axis(rightX), axis(rightY), batteryType, batteryLevel)
            } else {
                clearSlot(index)
            }
            if active && index == 0 && connected && settings.controllerMode == "keyboard" {
                if leftY > Float(settings.deadZone) || buttons & 1 != 0 { desiredKeys.insert(0x57) }
                if leftY < -Float(settings.deadZone) || buttons & 2 != 0 { desiredKeys.insert(0x53) }
                if leftX < -Float(settings.deadZone) || buttons & 4 != 0 { desiredKeys.insert(0x41) }
                if leftX > Float(settings.deadZone) || buttons & 8 != 0 { desiredKeys.insert(0x44) }
                let mapping: [(UInt16, Int32)] = [(0x1000,0x20),(0x2000,0x11),(0x4000,0x45),(0x8000,0x52),
                    (0x100,0x51),(0x200,0x10),(0x10,0x1B),(0x20,0x09),(0x40,0x10),(0x80,0x46)]
                for (mask, key) in mapping where buttons & mask != 0 { desiredKeys.insert(key) }
                if rightTrigger > 0.25 { desiredMouse |= 1 }
                if leftTrigger > 0.25 { desiredMouse |= 2 }
                let mouseX = Int32(Double(axis(rightX)) / 32767 * settings.mouseSpeed)
                let mouseY = Int32(-Double(axis(rightY)) / 32767 * settings.mouseSpeed)
                if mouseX != 0 || mouseY != 0 { winios_pointer(mouseX, mouseY, 0x1, 0) }
            }
        }
        for key in heldKeys.subtracting(desiredKeys) { winios_post_key(key, 0) }
        for key in desiredKeys.subtracting(heldKeys) { winios_post_key(key, 1) }
        heldKeys = desiredKeys
        if desiredMouse & 1 != mouseButtons & 1 { winios_pointer(0, 0, desiredMouse & 1 != 0 ? 0x2 : 0x4, 0) }
        if desiredMouse & 2 != mouseButtons & 2 { winios_pointer(0, 0, desiredMouse & 2 != 0 ? 0x8 : 0x10, 0) }
        mouseButtons = desiredMouse
        if frame % 6 == 0 { devices = snapshots }
    }
}

struct EmulatorSettingsView: View {
    var showDone = true
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var settings = EmulatorSettings.shared
    @ObservedObject private var controllers = GameControllerManager.shared
    @ObservedObject private var input = InputSettings.shared
    @State private var testing = false

    var body: some View {
        NavigationStack {
            Form {
                if GameLibrary.shared.sessionStarted {
                    Text("A session is running. These controls change temporary session values only. Long-press a library card to save per-game settings for your next launch.")
                        .font(.caption).foregroundStyle(.secondary)
                }
                NavigationLink { graphicsPage } label: { Label("Graphics", systemImage: "display") }
                NavigationLink { controllersPage } label: { Label("Controllers", systemImage: "gamecontroller") }
                NavigationLink { touchPage } label: { Label("Touch & Mouse", systemImage: "hand.draw") }
                NavigationLink { generalPage } label: { Label("General", systemImage: "gearshape") }
                NavigationLink { runtimePage } label: { Label("Windows Runtime", systemImage: "shippingbox") }
                NavigationLink { aboutPage } label: { Label("About", systemImage: "info.circle") }
                NavigationLink { DiagnosticsView() } label: { Label("Diagnostics & Sharing", systemImage: "stethoscope") }
                Section("Library") {
                    Text("One card per game folder. Touch and hold a game to choose its EXE, graphics, controller mode, and runtime. Installers and redistributable folders are excluded.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
            .toolbar { if showDone { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } } }
            .sheet(isPresented: $testing) { ControllerTestView() }
        }
    }
    private var graphicsPage: some View {
        Form {
            Section("Graphics") {
                    Picker("Desktop resolution", selection: $settings.resolution) {
                        ForEach(EmulatorSettings.resolutions, id: \.self) { Text($0).tag($0) }
                    }
                    Text("Applies when starting a new Wine session. Restart the app first if a session is running. Games can select a different resolution in their own video settings.")
                        .font(.caption).foregroundStyle(.secondary)
                    Toggle("Show FPS", isOn: $settings.showFPS)
                    Picker("Presentation pacing", selection: $settings.presentationMode) {
                        Text("60 FPS limit").tag(Int32(1))
                        Text("Display maximum").tag(Int32(0))
                        Text("Uncapped / frame skipping").tag(Int32(2))
                    }
                    Text("This controls presentation pacing, not guaranteed game performance.")
                        .font(.caption).foregroundStyle(.secondary)
                }
        }.navigationTitle("Graphics")
    }

    private var controllersPage: some View {
        Form {
            Section("Controllers") {
                    Picker("Game input", selection: $settings.controllerMode) {
                        Text("Xbox-compatible (XInput)").tag("xinput")
                        Text("Keyboard & mouse fallback").tag("keyboard")
                    }
                    if controllers.devices.isEmpty {
                        Text("No controller connected. Pair your Backbone or other controller in iOS Bluetooth settings, or connect it by cable.")
                            .foregroundStyle(.secondary)
                    }
                    ForEach(controllers.devices) { device in
                        VStack(alignment: .leading) {
                            Label("Player \(device.id + 1): \(device.name)", systemImage: "gamecontroller")
                            Text(device.battery).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                    Button("Test controller") { testing = true }
                    LabeledContent("Stick dead zone", value: "\(Int(settings.deadZone * 100))%")
                    Slider(value: $settings.deadZone, in: 0...0.5, step: 0.01)
                    Text("XInput supports four controllers, both sticks, triggers and standard buttons. DirectInput-only games can use keyboard fallback. Rumble and controller audio are not implemented.")
                        .font(.caption).foregroundStyle(.secondary)
                    if settings.controllerMode == "keyboard" {
                        Text("Player 1: left stick / D-pad = WASD; A = Space, B = Ctrl, X = E, Y = R; LB = Q, RB/L3 = Shift, R3 = F; Menu = Esc, View = Tab. Right stick = mouse; RT/LT = left/right click.")
                            .font(.caption)
                        Slider(value: $settings.mouseSpeed, in: 1...20) { Text("Right-stick mouse speed") }
                    }
                }
        }.navigationTitle("Controllers")
    }

    private var touchPage: some View {
        Form {
            Section("Touch & mouse") {
                    Toggle("Relative mouse mode", isOn: $input.relative)
                    LabeledContent("Pointer sensitivity", value: String(format: "%.2f", input.sensAbs))
                    Slider(value: $input.sensAbs, in: 0.1...8)
                    LabeledContent("Mouse-look sensitivity", value: String(format: "%.2f", input.sensRel))
                    Slider(value: $input.sensRel, in: 0.1...8)
                }
        }.navigationTitle("Touch & Mouse")
    }

    private var generalPage: some View {
        Form {
            Section("General") {
                    Toggle("Keep screen awake", isOn: $settings.keepAwake)
                    Toggle("Verbose diagnostics", isOn: $input.diagnostics)
                    Text("Settings and existing games stay in the same app container. Save states, CPU speed hacks, and DirectX 12 are not supported.")
                        .font(.caption).foregroundStyle(.secondary)
                }
        }.navigationTitle("General")
    }

    private var runtimePage: some View {
        Form {
            Section("Windows runtime help") {
                    Text("Touch and hold a game in Library, open Game Settings, then enable bundled ARM64 Visual C++. Restart the app before launching that game. You do not need to run the ARM64 installer.")
                    Text("The required Windows runtime depends on the game, not the iPhone CPU. This compatibility option does not guarantee that every game will run; the working Wine/x64 exception handlers are preserved.")
                        .font(.caption).foregroundStyle(.secondary)
                    Link("Microsoft runtime documentation", destination: URL(string: "https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist")!)
                }
        }.navigationTitle("Windows Runtime")
    }

    private var aboutPage: some View {
        Form {
            Section("About") {
                    Text("Something PC")
                        .font(.headline)
                    Text("Based on Madeira • Wine • FEX • DXMT")
                    Text("Unsigned builds require your existing signing and JIT setup.")
                        .font(.caption).foregroundStyle(.secondary)
                }
        }.navigationTitle("About")
    }

}

struct ControllerTestView: View {
    @Environment(\.dismiss) private var dismiss
    @ObservedObject private var controllers = GameControllerManager.shared

    var body: some View {
        NavigationStack {
            List {
                Text("Press buttons and move both sticks. Input is shown here and is not sent to your game while Settings is open.")
                    .font(.caption).foregroundStyle(.secondary)
                if controllers.devices.isEmpty { Text("Waiting for a controller…") }
                ForEach(controllers.devices) { device in
                    Section("Player \(device.id + 1) — \(device.name)") {
                        Text(device.battery)
                        LazyVGrid(columns: [GridItem(.adaptive(minimum: 62))]) {
                            ForEach(GameControllerManager.buttonMasks, id: \.0) { name, mask in
                                Text(name)
                                    .frame(maxWidth: .infinity, minHeight: 36)
                                    .background(device.buttons & mask != 0 ? Color.green.opacity(0.65) : Color.secondary.opacity(0.15))
                                    .clipShape(RoundedRectangle(cornerRadius: 8))
                            }
                        }
                        Text(String(format: "Left stick   X %+.2f   Y %+.2f", device.leftX, device.leftY))
                        Text(String(format: "Right stick  X %+.2f   Y %+.2f", device.rightX, device.rightY))
                        ProgressView("Left trigger", value: Double(device.leftTrigger))
                        ProgressView("Right trigger", value: Double(device.rightTrigger))
                    }
                }
            }
            .monospacedDigit()
            .navigationTitle("Controller Test")
            .toolbar { ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } } }
        }
    }
}

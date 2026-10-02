"""Apply app-only Steam/branding changes without changing native compiler inputs."""
from pathlib import Path
import json
import plistlib
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

DRIVER = Path(__file__).resolve().parent
LOCK = json.loads((DRIVER / 'source-lock.json').read_text())

def once(source, before, after):
    if source.count(before) != 1:
        raise ValueError('Unexpected pinned app marker: ' + before[:90])
    return source.replace(before, after, 1)

def brand(source):
    # Product-facing names; preserve runtime identifiers, logs and attribution.
    for before, after in (
        ('static let title = "Madeira"', 'static let title = "My-pc Native"'),
        ('.navigationTitle("Madeira")', '.navigationTitle("My-pc Native")'),
        ('Restart Madeira', 'Restart My-pc Native'),
        ('swipe Madeira away', 'swipe My-pc Native away'),
        ('Close Madeira', 'Close My-pc Native'),
        ('after Madeira restarts', 'after My-pc Native restarts'),
        ('Welcome to Madeira', 'Welcome to My-pc Native'),
        ('Madeira runs Windows games', 'My-pc Native runs Windows games'),
        ('Sign in to Steam in Madeira.', 'Sign in to Steam in My-pc Native.'),
        ('Dock, Madeira hands', 'Dock, My-pc Native hands'),
        ('Madeira keeps a Steam sign-in', 'My-pc Native keeps a Steam sign-in'),
        ('which Madeira downloads', 'which My-pc Native downloads'),
        ("in Madeira's drive_c", "in My-pc Native's drive_c"),
    ): source = source.replace(before, after)
    return source

def library_overlay(source):
    source = once(source, '            onboarding.presentIfNeeded()\n',
                  '            NativePerformance.libraryVisible()\n            onboarding.presentIfNeeded()\n')
    source = once(source, '    static let desktopID =', '''    static let steamDesktopID = UUID(uuidString: "1222C638-2B38-4985-A004-D6F60C2A5C79")!
    static var steamDesktopEntry: LibraryEntry {
        var entry = desktopEntry
        entry.id = steamDesktopID; entry.title = "Steam"; entry.resolution = "1280x720"
        entry.liveLogs = true; entry.graphicsAPI = "Desktop Steam through Wine/FEX"
        return entry
    }
    static let desktopID =''')
    source = once(source, '        if desktop == true { return "/desktop=shell,',
                  '        if id == Self.steamDesktopID { return "/desktop=shell,\\(resolution) cmd /c C:\\\\mypc-steam-desktop.bat" }\n        if desktop == true { return "/desktop=shell,')
    source = once(source, '    var startDock: (DockGame, Bool) -> Void = { _, _ in }',
                  '    var startDock: (DockGame, Bool) -> Void = { _, _ in }\n    var startSteamDesktop: () -> Void = {}\n    @ObservedObject private var desktopSteam = NativeSteamDesktopModel.shared')
    anchor = '                        .overlay(RoundedRectangle(cornerRadius: 22).stroke(focused == LibraryEntry.desktopID && controller.connected ? Color.cyan : .clear, lineWidth: 3))'
    source = once(source, anchor, anchor + '''
                    Button(action: startSteamDesktop) {
                        if liquidMetal.on {
                            let light = colorScheme == .light
                            steamDesktopLabel.font(.subheadline.weight(.semibold)).foregroundStyle(light ? .black : .white)
                                .shadow(color: (light ? Color.white : .black).opacity(0.75), radius: 2.5)
                                .padding(.horizontal, 14).frame(minHeight: 44).background(LiquidMetalFill())
                        } else {
                            steamDesktopLabel.font(.subheadline.weight(.medium)).padding(.horizontal, 14).frame(minHeight: 44)
                                .background(Color(uiColor: .secondarySystemGroupedBackground), in: Capsule())
                        }
                    }.buttonStyle(.plain).disabled(desktopSteam.busy)
                        .accessibilityLabel("Launch Steam")
                        .animation(UIAccessibility.isReduceMotionEnabled ? nil : .easeInOut(duration: 0.4), value: liquidMetal.on)
                        .id(LibraryEntry.steamDesktopID)
                        .overlay(RoundedRectangle(cornerRadius: 22).stroke(focused == LibraryEntry.steamDesktopID && controller.connected ? Color.cyan : .clear, lineWidth: 3))''')
    source = once(source, '    private var library: some View {', '''    private var steamDesktopLabel: some View {
        HStack(spacing: 7) {
            Image("SteamLogo").renderingMode(.template).resizable().scaledToFit().frame(width: 20, height: 20)
            Text("Launch Steam")
        }
    }
    private var library: some View {''')
    source = once(source, 'let ids = [LibraryEntry.desktopID] + items.map', 'let ids = [LibraryEntry.desktopID, LibraryEntry.steamDesktopID] + items.map')
    source = once(source, '                else { selected = items[index - 1] }',
                  '                else if index == 1 { startSteamDesktop() }\n                else { selected = items[index - 2] }')
    source = source.replace('!browser, !onboarding.presented else', '!browser, !onboarding.presented, !desktopSteam.presented else')
    source = source.replace('Flowing chrome on the bars and the Desktop button.', 'Flowing chrome on the bars, Desktop and Launch Steam buttons.')
    return brand(source)

def content_overlay(source):
    source = once(source, '    @State private var devSheet: SettingsSheet?',
                  '    @ObservedObject private var desktopSteam = NativeSteamDesktopModel.shared\n    @State private var devSheet: SettingsSheet?')
    source = once(source, 'startDock: { startDock($0, compactPool: $1) })',
                  'startDock: { startDock($0, compactPool: $1) }, startSteamDesktop: startSteamDesktop)')
    source = once(source, '            .navigationTitle("Madeira")',
                  '            .sheet(isPresented: $desktopSteam.presented) { NativeSteamDesktopSetupView() }\n            .navigationTitle("Madeira")')
    source = once(source, '            if dockLaunch.dock && SteamSignIn.flag(',
                  '            if profile?.id == LibraryEntry.steamDesktopID {\n                setenv("MADEIRA_DOCK_SESSION", "1", 1)\n            } else if dockLaunch.dock && SteamSignIn.flag(')
    source = once(source, '    private func launchLibraryEntry(_ entry: LibraryEntry) {',
                  '    private func launchLibraryEntry(_ entry: LibraryEntry) {\n        guard !desktopSteam.busy else { library.error = "Wait for desktop Steam setup to finish."; return }')
    source = once(source, '    private func startDock(_ game: DockGame, compactPool: Bool, profile: LibraryEntry? = nil) {',
                  '    private func startDock(_ game: DockGame, compactPool: Bool, profile: LibraryEntry? = nil) {\n        guard !desktopSteam.busy else { library.error = "Wait for desktop Steam setup to finish."; return }')
    source = once(source, '                try MadeiraDock.writeHandoff(account:',
                  '                try NativeSteamDesktopLaunch.restoreLibraryDiscovery(prefix: MadeiraDock.prefix)\n                try MadeiraDock.writeHandoff(account:')
    source = once(source, '    private func startWineserver() {', '''    private func startSteamDesktop() {
        guard !desktopSteam.busy else { return }
        guard jit_check_debugged() else { library.error = "Enable JIT in Settings before launching desktop Steam."; return }
        guard wine_process_is_running() == 0, wineserver_is_running() == 0, library.current == nil else {
            library.error = "A session is already running."; return
        }
        if LibraryModel.sessionsThisRun > 0, MadeiraConfig.flag("MADEIRA_ONE_SESSION_PER_RUN") {
            library.restartNotice = LibraryModel.restartMessage; return
        }
        desktopSteam.run {
            // Log off the native account connection before Steam's own login.
            await SteamOwnedLibrary.shared.prepareDock()
            try Task.checkCancellation()
            try await NativeSteamDesktopInstaller.shared.prepare(prefix: MadeiraDock.prefix) { value in
                await NativeSteamDesktopModel.shared.progress(value)
            }
            try Task.checkCancellation()
            guard jit_check_debugged(), wine_process_is_running() == 0, wineserver_is_running() == 0, library.current == nil else {
                throw NativeSteamDesktopFiles.fail("The launch state changed. Enable JIT and try again.")
            }
            try NativeSteamDesktopLaunch.prepare(prefix: MadeiraDock.prefix)
            let entry = LibraryEntry.steamDesktopEntry
            try entry.validate()
            unsetenv("MADEIRA_STEAM_APPID"); unsetenv("MADEIRA_STEAM_APPPATH"); unsetenv("MADEIRA_WORKDIR")
            unsetenv("MADEIRA_MADSYNC_SESSION")
            setenv("MADEIRA_GDI_SHARED_SECTION", "1", 1)
            logStore.log("[desktop-steam] launching full Windows Steam through Wine/FEX; native Linux VM=0")
            desktopSteam.presented = false
            library.begin(entry, remember: false)
            runWineFullSequence(profile: entry)
        }
    }

    private func startWineserver() {''')
    return brand(source)

def runtime_overlay(source):
    source = once(source, 'static func unpack(_ data: Data, write:', 'static func unpack(_ data: Data, desktop: Bool = false, write:')
    source = once(source, 'data.count <= 64 * 1024 * 1024', 'data.count <= (desktop ? 256 : 64) * 1024 * 1024')
    source = once(source, 'count <= 256)', 'count <= (desktop ? 16384 : 256))')
    source = once(source, 'size <= 64 * 1024 * 1024', 'size <= (desktop ? 512 : 64) * 1024 * 1024')
    source = once(source, 'total <= 256 * 1024 * 1024', 'total <= (desktop ? 1024 : 256) * 1024 * 1024')
    source = once(source, '        madeira_seed_prefix_if_needed(prefix.path)\n',
                  '        madeira_seed_prefix_if_needed(prefix.path)\n        try NativeSteamDesktopLaunch.restoreLibraryDiscovery(prefix: prefix)\n')
    return source

def project_overlay(source):
    source = source.replace('com.willfaust.madeora', LOCK['bundle_id']).replace('IPHONEOS_DEPLOYMENT_TARGET = 17.0;', f'IPHONEOS_DEPLOYMENT_TARGET = {LOCK["minimum_ios"]};')
    source = once(source, '/* Begin PBXBuildFile section */', '/* Begin PBXBuildFile section */\n\t\tA100F010 /* NativeSteamDesktop.swift in Sources */ = {isa = PBXBuildFile; fileRef = A200F010 /* NativeSteamDesktop.swift */; };')
    source = once(source, '/* Begin PBXFileReference section */', '/* Begin PBXFileReference section */\n\t\tA200F010 /* NativeSteamDesktop.swift */ = {isa = PBXFileReference; lastKnownFileType = sourcecode.swift; path = NativeSteamDesktop.swift; sourceTree = "<group>"; };')
    source = once(source, '\t\t\t\tA2000400 /* Library.swift */,', '\t\t\t\tA2000400 /* Library.swift */,\n\t\t\t\tA200F010 /* NativeSteamDesktop.swift */,')
    source = once(source, '\t\t\t\tA1000400 /* Library.swift in Sources */,', '\t\t\t\tA1000400 /* Library.swift in Sources */,\n\t\t\t\tA100F010 /* NativeSteamDesktop.swift in Sources */,')
    return source

def main(runtime):
    runtime = runtime.resolve()
    if runtime != (DRIVER / 'runtime').resolve(): raise ValueError('Only native-ios/runtime may be prepared')
    if subprocess.check_output(['git', '-C', str(runtime), 'rev-parse', 'HEAD'], text=True).strip() != LOCK['source']['commit']:
        raise ValueError('Unexpected app source revision')
    def original(path):
        return subprocess.check_output(['git', '-C', str(runtime), 'show', 'HEAD:' + path]).decode('utf-8')
    # Preflight all pinned markers, then write only app resources and Swift.
    pending = {
        'app/Madeira/Library.swift': library_overlay(original('app/Madeira/Library.swift')),
        'app/Madeira/ContentView.swift': content_overlay(original('app/Madeira/ContentView.swift')),
        'app/Madeira/SteamRuntime.swift': runtime_overlay(original('app/Madeira/SteamRuntime.swift')),
        'app/Madeira/Onboarding.swift': brand(original('app/Madeira/Onboarding.swift')),
        'app/Madeira.xcodeproj/project.pbxproj': project_overlay(original('app/Madeira.xcodeproj/project.pbxproj')),
    }
    icon = DRIVER / 'branding/AppIcon.png'
    if not icon.is_file(): raise ValueError('Missing My-pc icon')
    import hashlib
    if hashlib.sha1(b'blob ' + str(icon.stat().st_size).encode() + b'\0' + icon.read_bytes()).hexdigest() != 'be89650a004bae0da5bf44c551e3d75940df0902':
        raise ValueError('The My-pc icon differs from preview 33')
    svg = ET.fromstring((DRIVER / 'branding/SteamLogo.svg').read_text(encoding='utf-8'))
    svg.set('width', '89.333px'); svg.set('viewBox', '0 0 89.333 89.333')
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    info_path = runtime / 'app/Madeira/Info.plist'
    info = plistlib.loads(info_path.read_bytes()); info['CFBundleName'] = LOCK['display_name']; info['MyPCNativeDesktopSteam'] = True
    for path, source in pending.items(): (runtime / path).write_text(source, encoding='utf-8')
    shutil.copyfile(DRIVER / 'NativeSteamDesktop.swift', runtime / 'app/Madeira/NativeSteamDesktop.swift')
    shutil.copyfile(DRIVER / 'NativeApp.swift', runtime / 'app/Madeira/MadeiraApp.swift')
    assets = runtime / 'app/Madeira/Assets.xcassets'
    shutil.copyfile(icon, assets / 'AppIcon.appiconset/AppIcon.png')
    (assets / 'AppIcon.appiconset/Contents.json').write_text(json.dumps({'images': [{'filename': 'AppIcon.png', 'idiom': 'universal', 'platform': 'ios', 'size': '1024x1024'}], 'info': {'author': 'xcode', 'version': 1}}))
    steam = assets / 'SteamLogo.imageset'; steam.mkdir(exist_ok=True)
    (steam / 'SteamLogo.svg').write_bytes(ET.tostring(svg, encoding='utf-8', xml_declaration=True))
    (steam / 'Contents.json').write_text(json.dumps({'images': [{'filename': 'SteamLogo.svg', 'idiom': 'universal'}], 'info': {'author': 'xcode', 'version': 1}, 'properties': {'preserves-vector-representation': True, 'template-rendering-intent': 'template'}}))
    info_path.write_bytes(plistlib.dumps(info, sort_keys=False))

if __name__ == '__main__':
    main(Path(sys.argv[1]))
    print('Applied native desktop Steam launcher and My-pc branding')

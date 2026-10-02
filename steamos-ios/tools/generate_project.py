#!/usr/bin/env python3
"""Generate the deliberately small, new Xcode project without XcodeGen."""
import hashlib
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'MyPCSteamOS.xcodeproj'

def ident(value):
    return hashlib.sha256(value.encode()).hexdigest()[:24].upper()

def generate():
    project, target, group, product, products = map(ident, ['project', 'target', 'group', 'product', 'products'])
    sources, frameworks, resources = map(ident, ['sources', 'frameworks', 'resources'])
    objects = []
    files = ['Host/ProbeApp.swift', 'Host/ProbeBridge.mm', 'Host/ProbeBridge.h', 'Host/Info.plist']
    for path in files:
        kind = {'swift':'sourcecode.swift','mm':'sourcecode.cpp.objcpp','h':'sourcecode.c.h','plist':'text.plist.xml'}[path.rsplit('.',1)[1]]
        objects.append(f'{ident(path)} = {{isa = PBXFileReference; lastKnownFileType = {kind}; path = "{path}"; sourceTree = "<group>"; }};')
    compiled = files[:2]
    for path in compiled:
        objects.append(f'{ident("build:"+path)} = {{isa = PBXBuildFile; fileRef = {ident(path)}; }};')
    objects += [
        f'{product} = {{isa = PBXFileReference; explicitFileType = wrapper.application; path = MyPCSteamOSProbe.app; sourceTree = BUILT_PRODUCTS_DIR; }};',
        f'{products} = {{isa = PBXGroup; children = ({product},); name = Products; sourceTree = "<group>"; }};',
        f'{group} = {{isa = PBXGroup; children = ({",".join(ident(p) for p in files)},{products},); sourceTree = "<group>"; }};',
        f'{sources} = {{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({",".join(ident("build:"+p) for p in compiled)},); runOnlyForDeploymentPostprocessing = 0; }};',
        f'{frameworks} = {{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }};',
        f'{resources} = {{isa = PBXResourcesBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }};'
    ]
    for config in ['Debug', 'Release']:
        optimization = '-Onone' if config == 'Debug' else '-O'
        common = 'SDKROOT = iphoneos; IPHONEOS_DEPLOYMENT_TARGET = 26.0; CLANG_ENABLE_MODULES = YES; CLANG_ENABLE_OBJC_ARC = YES; CLANG_CXX_LANGUAGE_STANDARD = "c++17"; GCC_WARN_ABOUT_RETURN_TYPE = YES_ERROR;'
        objects.append(f'{ident("project:"+config)} = {{isa = XCBuildConfiguration; buildSettings = {{{common}}}; name = {config}; }};')
        settings = f'''{common}
ARCHS = arm64; TARGETED_DEVICE_FAMILY = "1,2"; SUPPORTED_PLATFORMS = iphoneos;
PRODUCT_BUNDLE_IDENTIFIER = com.aghjkshdsj.mypc.steamos.probe; PRODUCT_NAME = MyPCSteamOSProbe;
INFOPLIST_FILE = Host/Info.plist; GENERATE_INFOPLIST_FILE = NO;
SWIFT_VERSION = 5.0; SWIFT_OBJC_BRIDGING_HEADER = Host/ProbeBridge.h;
SWIFT_OPTIMIZATION_LEVEL = "{optimization}"; SWIFT_COMPILATION_MODE = wholemodule;
GCC_OPTIMIZATION_LEVEL = 2; ENABLE_DEBUG_DYLIB = NO; CODE_SIGN_STYLE = Automatic;
MPC_SOURCE_COMMIT = "local-unrecorded"; OTHER_LDFLAGS = "$(inherited) -framework Metal -framework GameController -framework UIKit";
'''
        objects.append(f'{ident("target:"+config)} = {{isa = XCBuildConfiguration; buildSettings = {{{settings}}}; name = {config}; }};')
    for name in ['project', 'target']:
        objects.append(f'{ident(name+":configs")} = {{isa = XCConfigurationList; buildConfigurations = ({ident(name+":Debug")},{ident(name+":Release")},); defaultConfigurationIsVisible = 0; defaultConfigurationName = Release; }};')
    objects += [
        f'{target} = {{isa = PBXNativeTarget; buildConfigurationList = {ident("target:configs")}; buildPhases = ({sources},{frameworks},{resources},); buildRules = (); dependencies = (); name = MyPCSteamOSProbe; productName = MyPCSteamOSProbe; productReference = {product}; productType = "com.apple.product-type.application"; }};',
        f'{project} = {{isa = PBXProject; attributes = {{LastUpgradeCheck = 2600; }}; buildConfigurationList = {ident("project:configs")}; compatibilityVersion = "Xcode 14.0"; developmentRegion = en; hasScannedForEncodings = 0; knownRegions = (en,Base,); mainGroup = {group}; productRefGroup = {products}; projectDirPath = ""; projectRoot = ""; targets = ({target},); }};'
    ]
    PROJECT.mkdir(parents=True, exist_ok=True)
    (PROJECT / 'project.pbxproj').write_text('// !$*UTF8*$!\n{ archiveVersion = 1; classes = {}; objectVersion = 56; objects = {\n' + '\n'.join(objects) + f'\n}}; rootObject = {project}; }}\n', encoding='utf-8')
    scheme = f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="2600" version="1.3">
<BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="MyPCSteamOSProbe.app" BlueprintName="MyPCSteamOSProbe" ReferencedContainer="container:MyPCSteamOS.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction>
<LaunchAction buildConfiguration="Release" selectedDebuggerIdentifier="" selectedLauncherIdentifier="Xcode.IDEFoundation.Launcher.PosixSpawn" launchStyle="0" useCustomWorkingDirectory="NO" ignoresPersistentStateOnLaunch="NO" debugDocumentVersioning="YES" debugServiceExtension="internal" allowLocationSimulation="NO"><BuildableProductRunnable runnableDebuggingMode="0"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{target}" BuildableName="MyPCSteamOSProbe.app" BlueprintName="MyPCSteamOSProbe" ReferencedContainer="container:MyPCSteamOS.xcodeproj"/></BuildableProductRunnable></LaunchAction>
<ProfileAction buildConfiguration="Release" shouldUseLaunchSchemeArgsEnv="YES" savedToolIdentifier="" useCustomWorkingDirectory="NO" debugDocumentVersioning="YES"/>
<AnalyzeAction buildConfiguration="Debug"/><ArchiveAction buildConfiguration="Release" revealArchiveInOrganizer="YES"/>
</Scheme>
'''
    directory = PROJECT / 'xcshareddata' / 'xcschemes'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'MyPCSteamOSProbe.xcscheme').write_text(scheme, encoding='utf-8')

if __name__ == '__main__':
    generate()

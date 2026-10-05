#!/usr/bin/env python3
"""Generate the separate fresh native-KMS app target with explicit source set."""
import hashlib
import pathlib
import plistlib
PROJECT=pathlib.Path(__file__).resolve().parents[1]
SOURCES=['NativeKMS/App.swift','NativeKMS/Gate.mm','NativeKMS/Surface.mm','NativeKMS/Receipt.mm','NativeKMS/FrameworkIdentity.mm',
    'Host/ProbeBridge.mm','Host/ProbeRecovery.mm','Host/RecoveryJournal.swift','Host/StikDebugRequest.swift',
    'Host/SystemCrashDiagnostics.swift','Host/GuestMetalTrace.mm','Host/NativeDisplayCompletion.mm']
def ident(text):return hashlib.sha256(text.encode()).hexdigest()[:24].upper()
def generate():
    output=PROJECT/'NativeKMS.xcodeproj';output.mkdir(exist_ok=False)
    rows=[]
    for path in SOURCES:
        kind='sourcecode.swift' if path.endswith('.swift') else 'sourcecode.cpp.objcpp'
        rows.append(f'{ident(path)} = {{isa=PBXFileReference; lastKnownFileType={kind}; path="{path}"; sourceTree="<group>";}};')
        rows.append(f'{ident("build"+path)} = {{isa=PBXBuildFile; fileRef={ident(path)};}};')
    def row(name,body):rows.append(f'{ident(name)} = {{'+body+'};')
    row('product','isa=PBXFileReference; explicitFileType=wrapper.application; path=MyPCSteamOSNativeKMS.app; sourceTree=BUILT_PRODUCTS_DIR;')
    row('products',f'isa=PBXGroup; name=Products; children=({ident("product")},); sourceTree="<group>";')
    row('group','isa=PBXGroup; children=('+','.join(ident(p) for p in SOURCES)+','+ident('products')+',); sourceTree="<group>";')
    row('sources','isa=PBXSourcesBuildPhase; buildActionMask=2147483647; files=('+','.join(ident('build'+p) for p in SOURCES)+',); runOnlyForDeploymentPostprocessing=0;')
    for name,isa in [('frameworks','PBXFrameworksBuildPhase'),('resources','PBXResourcesBuildPhase')]:
        row(name,f'isa={isa}; buildActionMask=2147483647; files=(); runOnlyForDeploymentPostprocessing=0;')
    for config in ['Debug','Release']:
        row('project'+config,f'isa=XCBuildConfiguration; name={config}; buildSettings={{SDKROOT=iphoneos; IPHONEOS_DEPLOYMENT_TARGET=26.0;}};')
        row('target'+config,f'''isa=XCBuildConfiguration; name={config}; buildSettings={{
            SDKROOT=iphoneos; IPHONEOS_DEPLOYMENT_TARGET=26.0; ARCHS=arm64; SUPPORTED_PLATFORMS=iphoneos;
            CLANG_ENABLE_OBJC_ARC=YES; CLANG_ENABLE_MODULES=YES; CLANG_CXX_LANGUAGE_STANDARD="c++17";
            PRODUCT_NAME=MyPCSteamOSNativeKMS; PRODUCT_BUNDLE_IDENTIFIER=com.aghjkshdsj.mypc.steamos.nativekms;
            INFOPLIST_FILE=NativeKMS/Info.plist; GENERATE_INFOPLIST_FILE=NO; SWIFT_VERSION=5.0;
            SWIFT_OBJC_BRIDGING_HEADER=NativeKMS/Bridge.h; SWIFT_OPTIMIZATION_LEVEL="-O";
            SWIFT_COMPILATION_MODE=wholemodule; GCC_OPTIMIZATION_LEVEL=2; DEBUG_INFORMATION_FORMAT="dwarf-with-dsym";
            ENABLE_DEBUG_DYLIB=NO; TARGETED_DEVICE_FAMILY="1,2"; MPC_SOURCE_COMMIT="local-unrecorded";
            OTHER_LDFLAGS="$(inherited) -framework Metal -framework QuartzCore -framework UIKit -framework MetricKit";
            LD_RUNPATH_SEARCH_PATHS="$(inherited) @executable_path/Frameworks";
            }};''')
    for name,prefix in [('projectConfigs','project'),('targetConfigs','target')]:
        row(name,f'isa=XCConfigurationList; buildConfigurations=({ident(prefix+"Debug")},{ident(prefix+"Release")},); defaultConfigurationIsVisible=0; defaultConfigurationName=Release;')
    row('target',f'isa=PBXNativeTarget; name=MyPCSteamOSNativeKMS; productName=MyPCSteamOSNativeKMS; productType="com.apple.product-type.application"; productReference={ident("product")}; buildConfigurationList={ident("targetConfigs")}; buildPhases=({ident("sources")},{ident("frameworks")},{ident("resources")},); buildRules=(); dependencies=();')
    row('project',f'isa=PBXProject; attributes={{LastUpgradeCheck=2600;}}; buildConfigurationList={ident("projectConfigs")}; compatibilityVersion="Xcode 14.0"; developmentRegion=en; knownRegions=(en,Base,); mainGroup={ident("group")}; productRefGroup={ident("products")}; projectDirPath=""; projectRoot=""; targets=({ident("target")},);')
    (output/'project.pbxproj').write_text('// !$*UTF8*$!\n{archiveVersion=1;classes={};objectVersion=56;objects={\n'+'\n'.join(rows)+'\n};rootObject='+ident('project')+';}\n',newline='\n')
    scheme=output/'xcshareddata/xcschemes';scheme.mkdir(parents=True)
    (scheme/'MyPCSteamOSNativeKMS.xcscheme').write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<Scheme LastUpgradeVersion="2600" version="1.3"><BuildAction parallelizeBuildables="YES" buildImplicitDependencies="YES"><BuildActionEntries><BuildActionEntry buildForTesting="YES" buildForRunning="YES" buildForProfiling="YES" buildForArchiving="YES" buildForAnalyzing="YES"><BuildableReference BuildableIdentifier="primary" BlueprintIdentifier="{ident('target')}" BuildableName="MyPCSteamOSNativeKMS.app" BlueprintName="MyPCSteamOSNativeKMS" ReferencedContainer="container:NativeKMS.xcodeproj"/></BuildActionEntry></BuildActionEntries></BuildAction></Scheme>\n''',newline='\n')
    info=plistlib.loads((PROJECT/'Host/Info.plist').read_bytes())
    info['CFBundleDisplayName']='My-pc Linux Display';info['CFBundleVersion']='4000029'
    info['UISupportedInterfaceOrientations']=['UIInterfaceOrientationPortrait']
    info['UIRequiresFullScreen']=True
    (PROJECT/'NativeKMS/Info.plist').write_bytes(plistlib.dumps(info))
if __name__=='__main__':generate()

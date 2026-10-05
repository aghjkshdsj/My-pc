#!/usr/bin/env python3
"""Build pinned upstream ARM Linux compositor; never claim phone/desktop proof."""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tarfile
from stage_guest_runtime import capture,digest,needed,package,fetch_sources
PROJECT=pathlib.Path(__file__).resolve().parents[1]
PINS={
 'wayland':('https://gitlab.freedesktop.org/wayland/wayland.git','1.24.0','736d12ac67c20c60dc406dc49bb06be878501f86'),
 'wayland-protocols':('https://gitlab.freedesktop.org/wayland/wayland-protocols.git','1.47','88223018d1b578d0d8869866da66d9608e05f928'),
 'libdrm':('https://gitlab.freedesktop.org/mesa/drm.git','libdrm-2.4.129','a8e5e10a873f67f557dc70e5407af4553f35edd9'),
 'pixman':('https://gitlab.freedesktop.org/pixman/pixman.git','pixman-0.44.2','46655e15671e1ca62d699821d75a85d341d7229c'),
 'libxkbcommon':('https://github.com/xkbcommon/libxkbcommon.git','xkbcommon-1.8.0','76740e0c4583ae49675e7ba8213d31ee09aa00d2'),
 'libdisplay-info':('https://gitlab.freedesktop.org/emersion/libdisplay-info.git','0.2.0','66b802d05b374cd8f388dc6ad1e7ae4f08cb3300'),
 'wlroots':('https://gitlab.freedesktop.org/wlroots/wlroots.git','0.20.2','d783533489e1f75d6886c2ab5c5960090ef268f8')}
OPTIONS={
 'wayland':['-Dtests=false','-Ddocumentation=false'],
 'wayland-protocols':['-Dtests=false'],
 'libdrm':['-Dauto_features=disabled','-Dtests=false'],
 'pixman':['-Dtests=disabled','-Ddemos=disabled','-Dgtk=disabled','-Dlibpng=disabled','-Dopenmp=disabled'],
 'libxkbcommon':['-Denable-tools=false','-Denable-x11=false','-Denable-docs=false','-Denable-xkbregistry=false','-Denable-wayland=false','-Dxkb-config-root=/usr/share/X11/xkb'],
 'libdisplay-info':[],
 'wlroots':['-Dauto_features=disabled','-Drenderers=vulkan','-Dbackends=drm,libinput','-Dallocators=gbm','-Dsession=enabled','-Dxwayland=disabled','-Dlibliftoff=disabled','-Dcolor-management=disabled']}

def run(*args,**kw):subprocess.run(args,check=True,**kw)
def arm(path):
 data=path.read_bytes();assert data[:6]==b'\x7fELF\x02\x01' and int.from_bytes(data[18:20],'little')==183,path

def pc_files(stage,output):
 """Relocate only build metadata, retaining /usr as the installed guest prefix."""
 output.mkdir(exist_ok=True)
 for p in stage.rglob('*.pc'):
  text=p.read_text();assert re.search(r'^prefix=/usr$',text,re.M),p
  text=re.sub(r'^([A-Za-z_][A-Za-z_0-9]*)=(/usr(?:/[^\n]*)?)$',
    lambda m:m[1]+'='+str(stage)+m[2],text,flags=re.M)
  (output/p.name).write_text(text)

def close_runtime(root,executables,source_output):
 directory=root/'usr/lib';cache={}
 for line in capture('ldconfig','-p').splitlines():
  match=re.match(r'\s*(\S+)\s+\([^)]*AArch64[^)]*\)\s+=>\s+(\S+)',line,re.I)
  if match:cache.setdefault(match[1],pathlib.Path(match[2]))
 queue=[p for p in directory.rglob('*') if p.is_file() and not p.is_symlink() and p.read_bytes()[:4]==b'\x7fELF']+executables
 checked=set();copied={}
 while queue:
  path=queue.pop().resolve(strict=True)
  if path in checked:continue
  checked.add(path);arm(path)
  for name in needed(path):
   assert pathlib.PurePosixPath(name).name==name
   target=directory/name
   if not target.is_file():
    original=cache[name];row=package(original);shutil.copy2(original.resolve(strict=True),target)
    notice=pathlib.Path('/usr/share/doc')/row['binary'].split(':')[0]/'copyright';assert notice.is_file()
    dest=root/'usr/share/doc'/row['binary'].split(':')[0]/'copyright';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(notice,dest)
    copied[name]={**row,'bytes':target.stat().st_size,'sha256':digest(target),'copyright_sha256':digest(dest)}
   queue.append(target)
 loader=pathlib.Path('/lib/ld-linux-aarch64.so.1');row=package(loader)
 destination=root/'lib/ld-linux-aarch64.so.1';destination.parent.mkdir(exist_ok=True);assert not destination.exists()
 shutil.copy2(loader.resolve(strict=True),destination);copied['loader']={**row,'sha256':digest(destination)}
 listings={}
 for path in sorted(checked):
  text=capture(str(destination),'--inhibit-cache','--library-path',str(directory),'--list',str(path))
  assert 'not found' not in text
  for resolved in re.findall(r'=>\s+(/\S+)',text):assert pathlib.Path(resolved).is_relative_to(root),(path,resolved)
  listings[str(path.relative_to(root))]=text
 return dict(files=copied,loader_listings=listings,distribution_sources=fetch_sources(list(copied.values()),source_output))

def build(mesa):
 assert os.uname().sysname=='Linux' and os.uname().machine=='aarch64'
 output=PROJECT/'out/guest-compositor';output.mkdir(parents=True,exist_ok=False)
 sources=output/'sources';sources.mkdir();stage=output/'runtime';stage.mkdir();metadata=output/'build-pkgconfig'
 # Reuse the exact Mesa already used in the accepted disposable ARM guest.
 with tarfile.open(mesa/'Guest-Mesa-Userspace.tar.gz') as archive:
  members=[m for m in archive if m.name=='receipt.json' or m.name=='staging' or m.name.startswith('staging/')]
  assert sum(m.size for m in members)<256*1024*1024
  for m in members:
   p=pathlib.PurePosixPath(m.name);assert not p.is_absolute() and '..' not in p.parts and (m.isfile() or m.isdir() or m.issym())
   if m.issym():assert not pathlib.PurePosixPath(m.linkname).is_absolute() and '..' not in pathlib.PurePosixPath(m.linkname).parts
  archive.extractall(output/'mesa-input',members=members,filter='data')
 receipt=json.loads((output/'mesa-input/receipt.json').read_text())
 assert receipt['source_commit']=='9ddc641f25d83a230affb90c7e59174a041bde30' and int(receipt['workflow_run'])==37074804870
 for name,row in receipt['files'].items():
  if name.startswith('staging/'):
   p=output/'mesa-input'/name;assert p.stat().st_size==row['bytes'] and digest(p)==row['sha256'],name
 shutil.copytree(output/'mesa-input/staging',stage,dirs_exist_ok=True,symlinks=True)
 assert (stage/'usr/lib/libgbm.so.1.0.0').is_file()
 env=dict(os.environ,PKG_CONFIG_PATH=str(metadata),LD_LIBRARY_PATH=str(stage/'usr/lib'),PATH=str(stage/'usr/bin')+':'+os.environ['PATH'])
 upstream={}
 for name,(url,tag,commit) in PINS.items():
  source=sources/name;run('git','clone','--depth','1','--branch',tag,url,str(source))
  assert capture('git','-C',str(source),'rev-parse','HEAD')==commit,name
  run('git','-C',str(source),'archive','--format=tar.gz','--output='+str(sources/(name+'-source.tar.gz')),'HEAD')
  license_paths=[p for p in source.iterdir() if p.is_file() and p.name in ['LICENSE','COPYING','COPYRIGHT']]
  if name=='libdrm':license_paths=[source/'xf86drm.c',source/'xf86drm.h'] # upstream retains per-file notices, no top-level COPYING
  assert license_paths,name
  upstream[name]=dict(url=url,tag=tag,commit=commit,archive_sha256=digest(sources/(name+'-source.tar.gz')),
    license_files={p.name:digest(p) for p in license_paths})
  pc_files(stage,metadata)
  directory=output/('build-'+name)
  opts=['--prefix=/usr','--libdir=lib','--buildtype=release','--wrap-mode=nofallback',*OPTIONS[name]]
  run('meson','setup',str(directory),str(source),*opts,env=env)
  run('meson','compile','-C',str(directory),'-j','3',*(['tinywl'] if name=='wlroots' else []),env=env)
  if name=='wlroots':
   # Only compositor/library targets were built, not all optional example apps.
   run('meson','install','-C',str(directory),'--destdir',str(stage),'--no-rebuild','--tags','runtime,devel',env=env)
   (stage/'usr/bin').mkdir(exist_ok=True);shutil.copy2(directory/'tinywl/tinywl',stage/'usr/bin/tinywl')
  else:run('meson','install','-C',str(directory),'--destdir',str(stage),env=env)
  upstream[name]['options']=opts
  upstream[name]['dependency_introspection']=json.loads((directory/'meson-info/intro-dependencies.json').read_text())
 # Explicit feature checks prevent an accidentally omitted renderer/backend.
 config=(output/'build-wlroots/include/wlr/config.h').read_text()
 for key in ['WLR_HAS_VULKAN_RENDERER','WLR_HAS_DRM_BACKEND','WLR_HAS_LIBINPUT_BACKEND','WLR_HAS_GBM_ALLOCATOR','WLR_HAS_SESSION']:
  assert re.search(r'^#define '+key+r' 1$',config,re.M),key
 assert re.search(r'^#define WLR_HAS_GLES2_RENDERER 0$',config,re.M)
 binary=stage/'usr/bin/tinywl';arm(binary)
 libraries=list((stage/'usr/lib').glob('libwlroots-0.20.so*'));assert libraries
 symbols=capture('nm','-D','--defined-only',str(libraries[0]))
 for name in ['wlr_vk_renderer_create_with_drm_fd','wlr_drm_backend_create']:assert name in symbols
 # Remove hosted build paths from movable guest ELF search paths.
 for path in [binary,*[p for p in stage.rglob('*') if p.is_file() and not p.is_symlink() and p.read_bytes()[:4]==b'\x7fELF']]:
  run('patchelf','--set-rpath','/usr/lib',str(path))
 closure=close_runtime(stage,[binary],output/'runtime-source')
 runtime_env=dict(env,WLR_BACKENDS='headless',WLR_RENDERER='vulkan',WLR_RENDER_DRM_DEVICE='/nonexistent-mypc-drm',
    XDG_RUNTIME_DIR=str(output/'session'),LIBSEAT_BACKEND='seatd')
 pathlib.Path(runtime_env['XDG_RUNTIME_DIR']).mkdir(mode=0o700)
 help_result=subprocess.run([str(binary),'-h'],env=runtime_env,capture_output=True,text=True,timeout=30)
 assert help_result.returncode==0 and 'Usage:' in help_result.stdout
 negative=subprocess.run([str(binary)],env=runtime_env,capture_output=True,text=True,timeout=30)
 text=negative.stdout+negative.stderr;(output/'missing-renderer.log').write_text(text)
 assert negative.returncode==1 and 'failed to create wlr_renderer' in text and 'Running Wayland compositor on' not in text
 print(text)
 result=dict(schema=1,scope='actual-source-built-arm-linux-wayland-compositor-compile-and-negative-controls',
  source_commit=os.environ.get('GITHUB_SHA'),workflow_run=os.environ.get('GITHUB_RUN_ID'),upstream=upstream,
  mesa_parent=dict(source=receipt['source_commit'],run=receipt['workflow_run']),runtime=closure,
  arm64_compiled=True,vulkan_drm_gbm_input_session_compiled=True,help_executed=True,missing_renderer_rejected=True,
  positive_compositor_started=False,phone_tested=False,steam_os_desktop_verified=False,steam_verified=False,game_fps_verified=False,
  files={p.relative_to(stage).as_posix():dict(bytes=p.stat().st_size,sha256=digest(p)) for p in stage.rglob('*') if p.is_file() and not p.is_symlink()})
 (output/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
 with tarfile.open(output/'Guest-Compositor-Runtime.tar.gz','w:gz') as t:t.add(stage,arcname='runtime');t.add(output/'receipt.json',arcname='receipt.json')
 with tarfile.open(output/'Guest-Compositor-Corresponding-Source.tar.gz','w:gz') as t:
  for p in sources.glob('*-source.tar.gz'):t.add(p,arcname=p.name)
  t.add(output/'runtime-source',arcname='runtime-source')
  t.add(mesa/'Guest-Mesa-Corresponding-Source.tar.gz',arcname='Guest-Mesa-Corresponding-Source.tar.gz')
  for name in ['tools/build_guest_compositor.py','tools/stage_guest_runtime.py']:t.add(PROJECT/name,arcname=name)
  t.add(PROJECT.parent/'.github/workflows/steamos-guest-compositor.yml',arcname='steamos-guest-compositor.yml')
  t.add(output/'receipt.json',arcname='receipt.json')
 print(json.dumps(dict(scope=result['scope'],arm64_compiled=True,missing_renderer_rejected=True,phone_tested=False)))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('mesa',type=pathlib.Path);build(p.parse_args().mesa.resolve())

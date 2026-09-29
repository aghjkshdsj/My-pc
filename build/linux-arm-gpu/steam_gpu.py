"""CI-only checks of Steam CEF's actual GPU and WebGL renderer.

Runs only in an isolated guest without a Steam account. Uses the documented
CDP SystemInfo.getInfo response, discarding command lines and target URLs.
"""
import contextlib
import json
import time
import urllib.parse
import urllib.request
from steam_cdp import login_target


WEBGL_STATE = '''(() => {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 16;
  const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
  if (!gl) return {available: false};
  const ext = gl.getExtension('WEBGL_debug_renderer_info');
  const renderer = String(gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
  gl.clearColor(1, 0, 0, 1); gl.clear(gl.COLOR_BUFFER_BIT);
  const pixel = new Uint8Array(4);
  gl.readPixels(8, 8, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  return {available: true, renderer, pixel: Array.from(pixel), error: gl.getError()};
})()'''


def renderer_is_virgl(renderer):
    value = str(renderer).lower()
    return ('virgl' in value and
            not any(name in value for name in ('llvmpipe', 'softpipe', 'swiftshader', 'software')))


def accelerated_state(gpu, webgl):
    attributes = gpu.get('auxAttributes', {})
    features = gpu.get('featureStatus', {})
    return (renderer_is_virgl(attributes.get('glRenderer', '')) and
            str(features.get('gpu_compositing', '')).startswith('enabled') and
            str(features.get('webgl', '')).startswith('enabled') and
            webgl.get('available') is True and renderer_is_virgl(webgl.get('renderer', '')) and
            webgl.get('pixel') == [255, 0, 0, 255] and webgl.get('error') == 0)


def request(endpoint, method, params=None):
    import websocket
    url = urllib.parse.urlsplit(endpoint)
    assert (url.scheme == 'ws' and url.hostname in {'localhost', '127.0.0.1'} and
            url.port == 8080), 'GPU diagnostic endpoint must be guest loopback'
    local = urllib.parse.urlunsplit(('ws', '127.0.0.1:8080', url.path, url.query, ''))
    with contextlib.closing(websocket.create_connection(local, timeout=5, suppress_origin=True)) as client:
        client.send(json.dumps({'id': 1, 'method': method, 'params': params or {}}))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = json.loads(client.recv())
            if result.get('id') == 1:
                assert 'error' not in result, 'CEF rejected the GPU diagnostic method'
                return result.get('result', {})
    raise RuntimeError('CEF GPU diagnostic timed out')


def accelerated_login():
    with urllib.request.urlopen('http://127.0.0.1:8080/json/version', timeout=5) as response:
        version = json.loads(response.read(1024 * 1024))
    gpu = request(version.get('webSocketDebuggerUrl', ''), 'SystemInfo.getInfo').get('gpu', {})
    with urllib.request.urlopen('http://127.0.0.1:8080/json/list', timeout=5) as response:
        targets = json.loads(response.read(1024 * 1024))
    state = {}
    for target in targets[:32]:
        if login_target(target):
            reply = request(target.get('webSocketDebuggerUrl', ''), 'Runtime.evaluate', {
                'expression': WEBGL_STATE, 'returnByValue': True, 'timeout': 3000})
            state = reply.get('result', {}).get('value') or {}
            if state.get('available'):
                break
    attributes = gpu.get('auxAttributes', {})
    features = gpu.get('featureStatus', {})
    # Bounded diagnostics only: never print the CDP commandLine, URLs or values
    # from the login form. This guest has no credentials or saved account.
    summary = {
        'renderer': str(attributes.get('glRenderer', ''))[:256],
        'compositing': str(features.get('gpu_compositing', ''))[:64],
        'webgl_status': str(features.get('webgl', ''))[:64],
        'webgl_renderer': str(state.get('renderer', ''))[:256],
        'shader_readback_ok': state.get('pixel') == [255, 0, 0, 255] and state.get('error') == 0,
        'accelerated': accelerated_state(gpu, state),
    }
    print('MYPC_STEAM_GPU_INFO ' + json.dumps(summary), flush=True)
    assert summary['accelerated'], 'Steam CEF did not prove virgl compositing and WebGL'
    print('MYPC_STEAM_GPU_CEF_OK', flush=True)

"""Read-only readiness check for a disposable Steam test session's login UI."""
import contextlib
import json
import time
import urllib.parse
import urllib.request


LOGIN_STATE = '''(() => {
  const password = document.querySelector('input[type="password"]');
  const rect = password && password.getBoundingClientRect();
  return {hostname: location.hostname, title: document.title,
    readyState: document.readyState,
    passwordVisible: !!(rect && rect.width > 0 && rect.height > 0 &&
      getComputedStyle(password).visibility !== 'hidden')};
})()'''


def ready_login(state):
    return (isinstance(state, dict) and state.get('hostname') == 'steamloopback.host'
            and state.get('readyState') == 'complete' and state.get('passwordVisible') is True)


def login_interface(output):
    # Enabled only by the CI probe, not by the normal installed launcher.
    import websocket
    observations = []
    try:
        with urllib.request.urlopen('http://127.0.0.1:8080/json/list', timeout=3) as response:
            targets = json.loads(response.read(1024 * 1024))
        (output / 'cef-targets.json').write_text(json.dumps(targets, indent=2) + '\n')
        for target in targets[:32]:
            if target.get('type') != 'page' or urllib.parse.urlsplit(target.get('url', '')).hostname != 'steamloopback.host':
                continue
            url = urllib.parse.urlsplit(target.get('webSocketDebuggerUrl', ''))
            if url.scheme != 'ws' or url.hostname not in {'localhost', '127.0.0.1'} or url.port != 8080:
                continue
            endpoint = urllib.parse.urlunsplit(('ws', '127.0.0.1:8080', url.path, url.query, ''))
            try:
                with contextlib.closing(websocket.create_connection(endpoint, timeout=3, suppress_origin=True)) as client:
                    client.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
                        'expression': LOGIN_STATE, 'returnByValue': True, 'timeout': 2000}}))
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        reply = json.loads(client.recv())
                        if reply.get('id') != 1:
                            continue
                        state = reply.get('result', {}).get('result', {}).get('value')
                        observations.append({'title': target.get('title'), 'state': state,
                                             'error': reply.get('error')})
                        if ready_login(state):
                            return state
                        break
            except (OSError, ValueError, websocket.WebSocketException) as error:
                observations.append({'title': target.get('title'), 'error': str(error)})
    except (OSError, ValueError) as error:
        observations.append({'error': str(error)})
    finally:
        (output / 'cef-readiness.json').write_text(json.dumps(observations, indent=2) + '\n')
    return None

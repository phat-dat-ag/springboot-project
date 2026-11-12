"""Test-only control, mTLS metric fixture, notification receiver and HTTP probe."""
import base64
from collections import Counter
import http.server
import json
import os
from pathlib import Path
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request

BASE = Path('/lab')
STATE = {'breach': 0, 'notify_failures': 1, 'notifications': [], 'attempts': []}
LOCK = threading.Lock()


def request(spec):
    context = ssl.create_default_context(cafile='/pki/ca.pem')
    if spec.get('ca') == 'untrusted':
        context = ssl.create_default_context(cafile='/pki/untrusted-ca.pem')
    role = spec.get('role', 'probe')
    if role != 'none':
        context.load_cert_chain('/pki/' + role + '/client.crt', '/pki/' + role + '/client.key')
    headers = dict(spec.get('headers', {}))
    if spec.get('basic'):
        pair = os.environ['TEST_GRAFANA_USER'] + ':' + os.environ['TEST_GRAFANA_PASSWORD']
        headers['Authorization'] = 'Basic ' + base64.b64encode(pair.encode()).decode()
    body = spec.get('body')
    if body is not None:
        body = json.dumps(body).encode()
        headers['Content-Type'] = 'application/json'
    start = time.monotonic()
    try:
        req = urllib.request.Request(spec['url'], data=body, headers=headers, method=spec.get('method'))
        with urllib.request.urlopen(req, context=context, timeout=spec.get('timeout', 8)) as response:
            raw = response.read(2 * 1024 * 1024).decode()
            try:
                raw = json.loads(raw)
            except ValueError:
                pass
            return {'status': response.status, 'body': raw, 'ms': round((time.monotonic() - start) * 1000, 2)}
    except urllib.error.HTTPError as error:
        raw = error.read(65536).decode()
        try:
            raw = json.loads(raw)
        except ValueError:
            pass
        return {'status': error.code, 'body': raw, 'ms': round((time.monotonic() - start) * 1000, 2)}
    except (OSError, ValueError) as error:
        reason = getattr(error, 'reason', error)
        return {'status': 0, 'error': type(error).__name__, 'tls_rejected': isinstance(reason, ssl.SSLError),
                'verify_message': getattr(reason, 'verify_message', None)}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, payload, kind='application/json'):
        raw = payload.encode() if isinstance(payload, str) else json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/metrics':
            with LOCK:
                value = STATE['breach']
            self.reply(200, '# TYPE phase6b_breach gauge\n' + ''.join(
                'phase6b_breach{member="' + member + '"} ' + str(value) + '\n' for member in ['a', 'b']), 'text/plain')
        elif self.path == '/state':
            with LOCK:
                self.reply(200, STATE)
        else:
            self.reply(404, {})

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get('Content-Length', '0'))) or b'{}')
        if self.path == '/control':
            with LOCK:
                for key in ['breach', 'notify_failures']:
                    if key in data:
                        STATE[key] = data[key]
            self.reply(200, {'ok': True})
        elif self.path == '/notify':
            with LOCK:
                rejected = STATE['notify_failures'] > 0
                if rejected:
                    STATE['notify_failures'] -= 1
                record = {'utc': time.time(), 'http_status': 503 if rejected else 200, 'payload': data}
                STATE['attempts'].append(record)
                if not rejected:
                    STATE['notifications'].append(record)
                (BASE / 'evidence/notifications.json').write_text(json.dumps(STATE, indent=2))
            self.reply(503 if rejected else 200, {'accepted': not rejected})
        else:
            self.reply(404, {})


def serve():
    plain = http.server.ThreadingHTTPServer(('0.0.0.0', 8080), Handler)
    threading.Thread(target=plain.serve_forever, daemon=True).start()
    secure = http.server.ThreadingHTTPServer(('0.0.0.0', 8443), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain('/pki/probe/server.crt', '/pki/probe/server.key')
    context.load_verify_locations('/pki/ca.pem')
    context.verify_mode = ssl.CERT_REQUIRED
    secure.socket = context.wrap_socket(secure.socket, server_side=True)
    secure.serve_forever()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'request':
        print(json.dumps(request(json.load(sys.stdin))))
    elif len(sys.argv) > 1 and sys.argv[1] == 'batch':
        specs = json.load(sys.stdin)
        assert len(specs) <= 300
        print(json.dumps([request(spec) for spec in specs]))
    else:
        serve()

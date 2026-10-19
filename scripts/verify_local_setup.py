"""Initialize and smoke-test the local assignment through its HTTP API."""
import json
import secrets
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app.config import webhook_settings

BASE = 'http://127.0.0.1:8000'


def request(path, data=None, headers=None, form=False):
    headers = dict(headers or {})
    body = None
    if data is not None:
        body = (urlencode(data) if form else json.dumps(data)).encode()
        headers['Content-Type'] = ('application/x-www-form-urlencoded' if form else 'application/json')
    with urlopen(Request(BASE + path, data=body, headers=headers), timeout=10) as response:
        return json.load(response)


def main():
    for _ in range(30):
        try:
            health = request('/')
            break
        except (URLError, TimeoutError):
            time.sleep(1)
    else:
        raise RuntimeError('API did not start; inspect .local-setup/api.log')
    assert health == {'detail': 'Server running....'}, health
    for path in ('/docs', '/scalar', '/openapi.json'):
        with urlopen(BASE + path, timeout=10) as response:
            assert response.status == 200

    credentials_path = Path('.local-setup/login.json')
    if credentials_path.exists():
        credentials = json.loads(credentials_path.read_text())
    else:
        credentials = {'name': 'Local Developer', 'email': 'developer@example.com',
                       'password': secrets.token_urlsafe(24)}
        credentials_path.touch(mode=0o600)
        credentials_path.write_text(json.dumps(credentials, indent=2) + '\n')
    try:
        token = request('/user/token', {'username': credentials['email'], 'password': credentials['password']}, form=True)
    except HTTPError as error:
        if error.code not in (400, 401, 404):
            raise
        request('/user/signup', credentials)
        token = request('/user/token', {'username': credentials['email'], 'password': credentials['password']}, form=True)
    auth = {'Authorization': 'Bearer ' + token['access_token']}
    campaigns = request('/campaign/all')
    matches = [c for c in campaigns if c['name'] == 'Weekly Teacher Check-in']
    if len(matches) > 1:
        raise RuntimeError('Multiple seed campaigns exist; resolve before seeding.')
    if not matches:
        request('/campaign/', {'name': 'Weekly Teacher Check-in', 'status': 'Planned'}, auth)
    subprocess.run(['uv', 'run', 'python', '-m', 'scripts.seed'], check=True)
    subprocess.run(['uv', 'run', 'python', '-m', 'scripts.seed'], check=True)
    webhook_auth = {'X-Webhook-Secret': webhook_settings.WEBHOOK_SECRET}
    payload = {'provider': 'fake_provider', 'provider_event_id': 'local_setup_delivered_001',
               'provider_message_id': 'msg_out_001', 'status': 'delivered',
               'event_timestamp': datetime.now().isoformat()}
    event = request('/webhook/status', payload, webhook_auth)
    repeated = request('/webhook/status', payload, webhook_auth)
    assert event == repeated, 'Status webhook retry returned a different event'
    # Use a fresh provider message ID because inbound messages are not deduplicated.
    request('/webhook/message', {'provider': 'fake_provider',
            'provider_message_id': 'local_setup_in_' + secrets.token_hex(8),
            'sender_phone': '919876543210', 'content': 'Local setup check-in reply',
            'event_timestamp': datetime.now().isoformat()}, webhook_auth)
    request('/user/logout', headers=auth)
    try:
        request('/user/logout', headers=auth)
    except HTTPError as error:
        assert error.code == 400, error.code
    else:
        raise AssertionError('Logged-out token was accepted')
    print('Verified health, docs, login, authenticated campaign, repeated seed, both webhooks, status retry, and Redis logout.')


if __name__ == '__main__':
    main()

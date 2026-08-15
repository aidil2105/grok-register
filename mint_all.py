#!/usr/bin/env python3
"""Mint OAuth tokens for all accounts in keys/accounts.txt (SSO -> PKCE -> tokens)."""
import os, sys, json, re, time, hashlib, base64, secrets, urllib.parse
sys.path.insert(0, '/root/grok-register')
from curl_cffi import requests as cf_req

CLIENT_ID = 'b1a00492-073a-47ea-816f-4c329264a828'
REDIRECT_URI = 'http://127.0.0.1:56121/callback'
TOKEN_ENDPOINT = 'https://auth.x.ai/oauth2/token'
AUTHORIZE_URL = 'https://auth.x.ai/oauth2/authorize'
SCOPE = 'openid profile email offline_access grok-cli:access api:access'
AUTH_DIR = '/root/grok-register/auths'

def mint(email, sso):
    code_verifier = secrets.token_urlsafe(64)[:128]
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest()).rstrip(b'=').decode()
    sess = cf_req.Session(impersonate='chrome120')
    sess.cookies.set('sso', sso, domain='.x.ai')
    params = {
        'response_type': 'code', 'client_id': CLIENT_ID, 'redirect_uri': REDIRECT_URI,
        'code_challenge': code_challenge, 'code_challenge_method': 'S256',
        'scope': SCOPE, 'state': secrets.token_urlsafe(16),
    }
    auth_url = f'{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}'
    r = sess.get(auth_url, allow_redirects=False, timeout=30,
                 headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    consent_url = r.headers.get('location', '')
    if not consent_url:
        return None, f'no consent url, status {r.status_code}'
    r2 = sess.get(consent_url, timeout=30,
                  headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    form_inputs = {}
    for m in re.finditer(r'<input[^>]*name="([^"]+)"[^>]*value="([^"]*)"', r2.text):
        form_inputs[m.group(1)] = m.group(2)
    for m in re.finditer(r'<input[^>]*value="([^"]*)"[^>]*name="([^"]+)"', r2.text):
        if m.group(2) not in form_inputs:
            form_inputs[m.group(2)] = m.group(1)
    post_data = dict(form_inputs)
    post_data['action'] = 'approve'
    r3 = sess.post(AUTHORIZE_URL, data=post_data, allow_redirects=False, timeout=30,
                   headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    loc = r3.headers.get('location', '')
    if 'code=' not in loc:
        return None, f'no code in redirect, status {r3.status_code}'
    code = urllib.parse.parse_qs(urllib.parse.urlparse(loc).query).get('code', [None])[0]
    r4 = sess.post(TOKEN_ENDPOINT, data={
        'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI,
        'code_verifier': code_verifier, 'client_id': CLIENT_ID,
    }, timeout=30)
    if r4.status_code != 200:
        return None, f'token endpoint {r4.status_code}'
    data = r4.json()
    if not data.get('access_token'):
        return None, 'no access_token in response'
    return data, None

def main():
    os.makedirs(AUTH_DIR, exist_ok=True)
    accounts = []
    for line in open('/root/grok-register/keys/accounts.txt'):
        line = line.strip()
        if not line or ':' not in line:
            continue
        parts = line.split(':')
        if len(parts) >= 3:
            accounts.append((parts[0], parts[-1]))  # email, sso
    print(f'{len(accounts)} accounts to mint')
    for email, sso in accounts:
        safe = re.sub(r'[^a-zA-Z0-9]', '_', email)
        out = os.path.join(AUTH_DIR, f'xai-{safe}.json')
        if os.path.exists(out):
            print(f'[SKIP] {email} already minted')
            continue
        data, err = mint(email, sso)
        if err:
            print(f'[FAIL] {email}: {err}')
            continue
        rec = {
            'type': 'xai', 'auth_kind': 'oauth',
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token', ''),
            'expires_in': data.get('expires_in', 21600),
            'email': email,
            'base_url': 'https://cli-chat-proxy.grok.com/v1',
            'token_endpoint': TOKEN_ENDPOINT,
            'redirect_uri': REDIRECT_URI,
            'client_id': CLIENT_ID,
            'disabled': False, 'mint_method': 'pkce', 'protocol_flow': 'pkce',
            'headers': {'X-XAI-Token-Auth': 'xai-grok-cli', 'x-grok-client-version': '0.2.93', 'x-grok-client-identifier': 'grok-shell'},
        }
        with open(out, 'w') as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        print(f'[OK] {email} -> {out}')

if __name__ == '__main__':
    main()

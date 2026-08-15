#!/usr/bin/env python3
"""Test mail.tm inbox + webshare proxy: does xAI deliver codes to a NON-Gmail address?"""
import os, sys, time, re, struct, random, string
sys.path.insert(0, '/root/grok-register')
from curl_cffi import requests as cf_req

SITE_URL = 'https://accounts.x.ai'
PROXY = os.getenv("GROK_PROXY", "")

def enc(field, val):
    key = (field << 3) | 2
    vb = val.encode()
    payload = struct.pack('B', key) + struct.pack('B', len(vb)) + vb
    return b'\x00' + struct.pack('>I', len(payload)) + payload

# 1. create mail.tm inbox (no proxy needed for mail.tm API)
import requests as std_req
base = 'https://api.mail.tm'
domains = std_req.get(f'{base}/domains', timeout=15).json()
domain = (domains if isinstance(domains, list) else domains.get('hydra:member', []))[0]['domain']
user = 'grok' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
password = 'Gk' + ''.join(random.choices(string.ascii_letters + string.digits, k=14)) + '!1'
address = f'{user}@{domain}'
r = std_req.post(f'{base}/accounts', json={'address': address, 'password': password}, timeout=15)
print('mail.tm account:', r.status_code, address)
tok = std_req.post(f'{base}/token', json={'address': address, 'password': password}, timeout=15).json().get('token', '')
print('token:', bool(tok))

# 2. send code via webshare proxy
sess = cf_req.Session(impersonate='chrome120')
sess.proxies = {'http': PROXY, 'https': PROXY}
try: sess.get(SITE_URL, timeout=10)
except: pass
headers = {'content-type': 'application/grpc-web+proto', 'x-grpc-web': '1',
           'x-user-agent': 'connect-es/2.1.1', 'origin': SITE_URL,
           'referer': f'{SITE_URL}/sign-up?redirect=grok-com'}
r2 = sess.post(f'{SITE_URL}/auth_mgmt.AuthManagement/CreateEmailValidationCode',
               data=enc(1, address), headers=headers, timeout=15)
print('send:', r2.status_code, r2.content[:60])

# 3. poll mail.tm inbox
deadline = time.time() + 60
found = None
while time.time() < deadline:
    r3 = std_req.get(f'{base}/messages', headers={'Authorization': f'Bearer {tok}'}, timeout=15)
    msgs = r3.json().get('hydra:member', []) if r3.status_code == 200 else []
    if msgs:
        m = msgs[0]
        found = f'{m.get("subject")} | {m.get("intro")}'
        break
    time.sleep(8)
print('MAILTM GOT:', found if found else 'NOTHING in 60s')

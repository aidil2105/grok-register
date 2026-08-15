#!/usr/bin/env python3
"""Test: is xAI's email-code limit per-IP or per-account?
Sends codes via 3 fresh proxies to 3 fresh aliases, watches Gmail."""
import os, sys, time, re, struct, imaplib, email as email_mod
sys.path.insert(0, '/root/grok-register')
from curl_cffi import requests as cf_req

SITE_URL = 'https://accounts.x.ai'
GMAIL_USER = os.getenv("GMAIL_BASE_EMAIL", "")
GMAIL_PASS = open('/root/.gmail_app_password').read().splitlines()[1]

def enc(field, val):
    key = (field << 3) | 2
    vb = val.encode()
    payload = struct.pack('B', key) + struct.pack('B', len(vb)) + vb
    return b'\x00' + struct.pack('>I', len(payload)) + payload

def imap_latest_for(alias):
    c = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    c.login(GMAIL_USER, GMAIL_PASS)
    c.select('INBOX')
    _, d = c.uid('SEARCH', None, f'(FROM "x.ai" TO "{alias}")')
    u = d[0].split()
    if not u:
        c.logout()
        return None
    _, md = c.uid('FETCH', u[-1], '(BODY.PEEK[])')
    msg = email_mod.message_from_bytes(md[0][1])
    c.logout()
    return str(msg.get('Subject'))

def random_alias():
    import random, string
    return f'{GMAIL_USER.split("@")[0]}+grok{"".join(random.choices(string.ascii_lowercase+string.digits, k=10))}@gmail.com'

proxies = [l.strip() for l in open('/root/grok-register/keys/alive_now.txt') if l.strip()][:3]
print(f'testing {len(proxies)} proxies: {proxies}')

for p in proxies:
    alias = random_alias()
    print(f'\n=== {p} ===')
    print(f'  alias: {alias}')
    try:
        sess = cf_req.Session(impersonate='chrome120')
        sess.proxies = {'http': p, 'https': p}
        r0 = sess.get(SITE_URL, timeout=10)
        print(f'  accounts.x.ai via proxy: {r0.status_code}')
        headers = {'content-type': 'application/grpc-web+proto', 'x-grpc-web': '1',
                   'x-user-agent': 'connect-es/2.1.1', 'origin': SITE_URL,
                   'referer': f'{SITE_URL}/sign-up?redirect=grok-com'}
        r = sess.post(f'{SITE_URL}/auth_mgmt.AuthManagement/CreateEmailValidationCode',
                      data=enc(1, alias), headers=headers, timeout=15)
        print(f'  send: {r.status_code}')
        got = None
        for i in range(10):
            time.sleep(5)
            got = imap_latest_for(alias)
            if got:
                print(f'  [{i*5}s] EMAIL ARRIVED: {got}')
                break
        if not got:
            print('  NO EMAIL in 50s (rate limited / dropped)')
    except Exception as e:
        print(f'  ERR: {str(e)[:120]}')

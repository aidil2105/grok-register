#!/usr/bin/env python3
"""Parallel-test proxies for x.ai code DELIVERY (not just HTTP 200).
Sends one code per proxy to a fresh alias, marks good if email arrives in 30s."""
import os, sys, time, re, struct, imaplib, email as email_mod, random, string
import concurrent.futures
sys.path.insert(0, '/root/grok-register')
from curl_cffi import requests as cf_req

SITE_URL = 'https://accounts.x.ai'
GMAIL_USER = os.getenv("GMAIL_BASE_EMAIL", "")
GMAIL_PASS = open('/root/.gmail_app_password').read().splitlines()[1]
MAX_PROXIES = int(sys.argv[1]) if len(sys.argv) > 1 else 40

def enc(field, val):
    key = (field << 3) | 2
    vb = val.encode()
    payload = struct.pack('B', key) + struct.pack('B', len(vb)) + vb
    return b'\x00' + struct.pack('>I', len(payload)) + payload

def imap_find(alias, timeout=30):
    deadline = time.time() + timeout
    c = None
    while time.time() < deadline:
        try:
            c = imaplib.IMAP4_SSL('imap.gmail.com', 993)
            c.login(GMAIL_USER, GMAIL_PASS)
            c.select('INBOX')
            _, d = c.uid('SEARCH', None, f'(FROM "x.ai" TO "{alias}")')
            u = d[0].split()
            if u:
                _, md = c.uid('FETCH', u[-1], '(BODY.PEEK[])')
                msg = email_mod.message_from_bytes(md[0][1])
                c.logout()
                return str(msg.get('Subject'))
            c.logout()
        except Exception:
            try: c and c.logout()
            except: pass
        time.sleep(5)
    return None

def random_alias():
    return f'{GMAIL_USER.split("@")[0]}+grok{"".join(random.choices(string.ascii_lowercase+string.digits, k=10))}@gmail.com'

def test_proxy(proxy):
    alias = random_alias()
    try:
        sess = cf_req.Session(impersonate='chrome120')
        sess.proxies = {'http': proxy, 'https': proxy}
        try: sess.get(SITE_URL, timeout=10)
        except: return (proxy, 'dead')
        headers = {'content-type': 'application/grpc-web+proto', 'x-grpc-web': '1',
                   'x-user-agent': 'connect-es/2.1.1', 'origin': SITE_URL,
                   'referer': f'{SITE_URL}/sign-up?redirect=grok-com'}
        r = sess.post(f'{SITE_URL}/auth_mgmt.AuthManagement/CreateEmailValidationCode',
                      data=enc(1, alias), headers=headers, timeout=15)
        if r.status_code != 200:
            return (proxy, f'http{r.status_code}')
        subj = imap_find(alias, timeout=25)
        if subj and 'confirmation code' in subj:
            return (proxy, 'GOOD')
        return (proxy, 'nodrop')
    except Exception as e:
        return (proxy, 'err')

def main():
    proxies = [l.strip() for l in open('/root/grok-register/keys/webshare.txt') if l.strip()]
    random.shuffle(proxies)
    proxies = proxies[:MAX_PROXIES]
    print(f'testing {len(proxies)} proxies...')
    good = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        for proxy, status in ex.map(test_proxy, proxies):
            if status == 'GOOD':
                good.append(proxy)
                print(f'GOOD: {proxy}')
            else:
                print(f'  {status}: {proxy}')
    print(f'\ngood: {len(good)}/{len(proxies)}')
    with open('/root/grok-register/keys/code_live3.txt', 'w') as f:
        f.write('\n'.join(good))

if __name__ == '__main__':
    main()

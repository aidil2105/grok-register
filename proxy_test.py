#!/usr/bin/env python3
"""Parse proxy list, test against accounts.x.ai via curl_cffi, save working ones."""
import json, sys, concurrent.futures, time

d = json.load(open('/root/.hermes/cache/documents/doc_fdca9ab19bab_free-proxy-list.json'))
proxies = d['proxies']
print(f"total: {len(proxies)}")

# basic filter: alive, elite, low timeout
cands = [p for p in proxies if p.get('alive') and p.get('anonymity') in ('elite', 'anonymous') and p.get('average_timeout', 9999) < 3000]
# unique host:port
seen = set()
uniq = []
for p in cands:
    key = f"{p.get('ip')}:{p.get('port')}"
    if key not in seen:
        seen.add(key)
        uniq.append(p)
print(f"filtered unique: {len(uniq)}")

from curl_cffi import requests

def test_proxy(p):
    ip = p.get('ip'); port = p.get('port')
    proto = (p.get('protocols') or ['http'])[0]
    url = f"{proto}://{ip}:{port}"
    try:
        s = requests.Session(impersonate='chrome120')
        s.proxies = {"http": url, "https": url}
        r = s.get('https://accounts.x.ai/', timeout=8)
        if r.status_code == 200:
            return (ip, port, proto, 200, len(r.text))
        return (ip, port, proto, r.status_code, 0)
    except Exception as e:
        return (ip, port, proto, 'ERR', str(e)[:40])

good = []
with concurrent.futures.ThreadPoolExecutor(max_workers=60) as ex:
    for res in ex.map(test_proxy, uniq[:400]):
        if res[3] == 200:
            good.append(res)
            print("GOOD:", res[0], res[1], res[2], "len:", res[4])

print(f"\nworking 200: {len(good)}")
with open('/root/grok-register/keys/good_proxies.txt', 'w') as f:
    for g in good:
        f.write(f"{g[2]}://{g[0]}:{g[1]}\n")

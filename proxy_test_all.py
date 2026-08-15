#!/usr/bin/env python3
"""Test ALL proxies in the list against accounts.x.ai, keep working ones with fast times."""
import json, concurrent.futures, time

d = json.load(open('/root/.hermes/cache/documents/doc_fdca9ab19bab_free-proxy-list.json'))
proxies = d['proxies']
seen = set()
uniq = []
for p in proxies:
    if not p.get('alive'):
        continue
    key = f"{p.get('ip')}:{p.get('port')}"
    if key not in seen:
        seen.add(key)
        uniq.append(p)
print(f"total unique alive: {len(uniq)}")

from curl_cffi import requests

def test_proxy(p):
    ip = p.get('ip'); port = p.get('port')
    proto = (p.get('protocols') or ['http'])[0]
    url = f"{proto}://{ip}:{port}"
    t0 = time.time()
    try:
        s = requests.Session(impersonate='chrome120')
        s.proxies = {"http": url, "https": url}
        r = s.get('https://accounts.x.ai/', timeout=10)
        dt = time.time() - t0
        if r.status_code == 200:
            return (ip, port, proto, 200, round(dt, 2))
        return (ip, port, proto, r.status_code, round(dt, 2))
    except Exception:
        return (ip, port, proto, 'ERR', 0)

good = []
with concurrent.futures.ThreadPoolExecutor(max_workers=80) as ex:
    for res in ex.map(test_proxy, uniq):
        if res[3] == 200:
            good.append(res)

good.sort(key=lambda x: x[4])
print(f"working 200: {len(good)}")
for g in good[:30]:
    print(" ", g[2], g[0], g[1], f"{g[4]}s")
with open('/root/grok-register/keys/good_proxies.txt', 'w') as f:
    for g in good:
        f.write(f"{g[2]}://{g[0]}:{g[1]}\n")

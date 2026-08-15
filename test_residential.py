#!/usr/bin/env python3
"""Test residential-looking proxies for speed + Cloudflare pass."""
import json, concurrent.futures, time
from curl_cffi import requests

d = json.load(open('/root/.hermes/cache/documents/doc_fdca9ab19bab_free-proxy-list.json'))
# all working proxies from previous test
working = set()
for line in open('/root/grok-register/keys/good_proxies.txt'):
    working.add(line.strip())

def test_proxy(p):
    key = f"{p.get('protocols',['http'])[0]}://{p.get('ip')}:{p.get('port')}"
    if key not in working:
        return None
    ipd = p.get('ip_data', {})
    asname = ipd.get('asname', '')
    # residential-looking ASNs (ISP/mobile, not hosting)
    resid_keywords = ['MOBILE', 'EXTREMEBB', 'CONVERGE', 'GLOBE', 'TTNET', 'TMOBILE', 'CHINANET', 'UNICORN', 'FIBRA', 'CABLE', 'TELLCOM', 'VIETEL', 'IPG-AS', 'INFINIVAN', 'ETB', 'MULTICARRIER', 'Mega Cable', 'TAPIA', 'Telconet', 'UFINET', 'UNE EPM', 'SISTEMAS', 'PEGASO', 'SUPER REDES', 'TRANSTELCO', 'CITYNET', 'KTVAIDA', 'SKB-AS', 'Jair', 'ILLINOIS-CENTURY', 'WEBAIR']
    if not any(k in asname.upper() for k in [x.upper() for x in resid_keywords]):
        return None
    t0 = time.time()
    try:
        s = requests.Session(impersonate='chrome120')
        s.proxies = {"http": key, "https": key}
        r = s.get('https://accounts.x.ai/', timeout=10)
        dt = time.time() - t0
        return (key, asname, ipd.get('country',''), r.status_code, round(dt,2))
    except Exception:
        return (key, asname, ipd.get('country',''), 'ERR', 0)

results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
    for res in ex.map(test_proxy, d['proxies']):
        if res:
            results.append(res)

results.sort(key=lambda x: (x[3] != 200, x[4]))
for r in results:
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}s")

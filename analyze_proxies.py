#!/usr/bin/env python3
import json
d = json.load(open('/root/.hermes/cache/documents/doc_fdca9ab19bab_free-proxy-list.json'))
working = set()
for line in open('/root/grok-register/keys/good_proxies.txt'):
    working.add(line.strip().split('://')[1])
rows = []
for p in d['proxies']:
    key = f"{p.get('ip')}:{p.get('port')}"
    if key in working:
        ipd = p.get('ip_data', {})
        rows.append((ipd.get('asname', ''), ipd.get('country', ''), ipd.get('city', ''), key))
for r in sorted(set(rows)):
    print(r)

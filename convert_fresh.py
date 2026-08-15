#!/usr/bin/env python3
"""Convert fresh proxy list (ipport format) to http:// URLs and dedupe against existing."""
import sys

src = '/tmp/fresh_proxies.txt'
out = '/root/grok-register/keys/fresh_urls.txt'
seen = set()
with open(src) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        if line.startswith('http'):
            url = line
        else:
            url = f'http://{line}'
        if url not in seen:
            seen.add(url)
            print(url)
with open(out, 'w') as f:
    f.write('\n'.join(sorted(seen)))
print(f'wrote {len(seen)} to {out}')

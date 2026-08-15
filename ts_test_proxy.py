#!/usr/bin/env python3
"""Test whether Turnstile solves through a proxy via manual render (repo's method)."""
import sys, os, asyncio, json, time
sys.path.insert(0, '/root/grok-register')
from turnstile_solver_local import solve_turnstile

async def main():
    proxy = sys.argv[1]
    print(f"testing turnstile through {proxy}")
    os.environ['GROK_PROXY'] = proxy
    r = await solve_turnstile(
        'https://accounts.x.ai/sign-up?redirect=grok-com',
        '0x4AAAAAAAhr9JGVDZbrZOo0',
        trigger_selector='__xai_email__',
        headless=False,
        captcha_timeout=60,
    )
    print("RESULT:", json.dumps(r)[:200])

asyncio.run(main())

#!/usr/bin/env python3
"""CDP: load signup through proxy, inject turnstile script, render, poll for solve."""
import asyncio, json, urllib.request, sys
import websockets

SITE_KEY = "0x4AAAAAAAhr9JGVDZbrZOo0"

async def main():
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=20*1024*1024, open_timeout=5)
    mid = 0
    async def cmd(method, params=None, timeout=30):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if msg.get("id") == mid:
                return msg
    async def ev(expr):
        r = await cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("result", {}).get("value")

    await cmd("Page.enable")
    await cmd("Runtime.enable")
    await cmd("Page.navigate", {"url": "https://accounts.x.ai/sign-up?redirect=grok-com"})
    await asyncio.sleep(8)
    # dismiss cookies + click email option
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    t = await ev("document.body.innerText.slice(0, 200)")
    print("PAGE:", t.replace("\n", " | ")[:150])
    print("turnstile global:", await ev("typeof turnstile"))

    # inject turnstile API script if missing
    has_api = await ev("typeof turnstile !== 'undefined'")
    if not has_api:
        print("injecting turnstile script...")
        r = await ev("""new Promise((res) => {
            const s = document.createElement('script');
            s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=tsOnLoad';
            window.tsOnLoad = () => res('loaded');
            s.onerror = () => res('error');
            document.head.appendChild(s);
            setTimeout(() => res('timeout'), 15000);
        })""")
        print("script:", r)
    await asyncio.sleep(2)
    print("turnstile global now:", await ev("typeof turnstile"))

    # render widget
    r = await ev(f"""new Promise((resolve) => {{
        if (typeof turnstile === 'undefined') {{ resolve('no-api'); return; }}
        const div = document.createElement('div');
        div.id = 'ts-test';
        div.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999';
        document.body.appendChild(div);
        let done = false;
        try {{
            turnstile.render('#ts-test', {{
                sitekey: '{SITE_KEY}',
                theme: 'light',
                callback: function(token) {{
                    if (!done) {{ done = true; resolve('solved:' + token.length); }}
                }},
                'error-callback': function(e) {{
                    if (!done) {{ done = true; resolve('err:' + JSON.stringify(e)); }}
                }},
                'expired-callback': function() {{
                    if (!done) {{ done = true; resolve('expired'); }}
                }}
            }});
            setTimeout(() => {{ if (!done) {{ done = true; resolve('timeout'); }} }}, 45000);
        }} catch(e) {{
            resolve('exception:' + e.message);
        }}
    }})""")
    print("TS RESULT:", r)

asyncio.run(main())

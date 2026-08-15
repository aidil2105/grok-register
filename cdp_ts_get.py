#!/usr/bin/env python3
"""Step A: load page through proxy, click email option, inject turnstile script, render, save token."""
import asyncio, json, urllib.request, sys
import websockets

SITE_KEY = "0x4AAAAAAAhr9JGVDZbrZOo0"
STATE_FILE = "/root/grok-register/keys/ts_token.txt"

async def main():
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=10))
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=20*1024*1024, open_timeout=10)
    mid = 0
    async def cmd(method, params=None, timeout=90):
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
    await asyncio.sleep(15)
    t = await ev("document.body.innerText.slice(0, 150)")
    print("PAGE:", t.replace("\n", " | ")[:120])

    # dismiss cookies if present
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    # click email option
    clicked = await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    print("clicked email:", clicked)
    await asyncio.sleep(5)
    t = await ev("document.body.innerText.slice(0, 200)")
    print("PAGE2:", t.replace("\n", " | ")[:150])

    # inject turnstile script and wait for load
    r = await ev("""new Promise((res) => {
        if (typeof turnstile !== 'undefined') { res('already'); return; }
        const s = document.createElement('script');
        s.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?onload=tsOnLoad';
        window.tsOnLoad = () => res('loaded');
        s.onerror = () => res('error');
        document.head.appendChild(s);
        setTimeout(() => res('timeout'), 25000);
    })""")
    print("script load:", r)
    await asyncio.sleep(1)
    print("turnstile global:", await ev("typeof turnstile"))

    # render widget and wait for token
    r = await ev(f"""new Promise((resolve) => {{
        if (typeof turnstile === 'undefined') {{ resolve('no-api'); return; }}
        const div = document.createElement('div');
        div.id = 'ts-widget';
        div.style.cssText = 'position:fixed;top:10px;right:10px;z-index:99999;width:300px;height:65px;background:#fff;border:1px solid #ccc';
        document.body.appendChild(div);
        let done = false;
        try {{
            turnstile.render('#ts-widget', {{
                sitekey: '{SITE_KEY}',
                theme: 'light',
                callback: function(token) {{
                    if (!done) {{ done = true; resolve('solved:' + token); }}
                }},
                'error-callback': function(e) {{
                    if (!done) {{ done = true; resolve('err:' + JSON.stringify(e)); }}
                }},
                'expired-callback': function() {{
                    if (!done) {{ done = true; resolve('expired'); }}
                }}
            }});
            setTimeout(() => {{ if (!done) {{ done = true; resolve('timeout'); }} }}, 60000);
        }} catch(e) {{
            resolve('exception:' + e.message);
        }}
    }})""")
    print("TS:", r[:80])
    if r.startswith("solved:"):
        token = r.split(":", 1)[1]
        with open(STATE_FILE, "w") as f:
            f.write(token)
        print("TOKEN SAVED, len:", len(token))
    # screenshot
    shot = await cmd("Page.captureScreenshot", {"format": "png"}, timeout=30)
    if shot.get("data"):
        import base64
        with open("/tmp/grok_ts_state.png", "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("SHOT saved")

asyncio.run(main())

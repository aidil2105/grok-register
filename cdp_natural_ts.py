#!/usr/bin/env python3
"""Quick natural Turnstile test through current proxy: load signup, click email, poll for token/iframe."""
import asyncio, json, urllib.request, sys
import websockets

async def main():
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=20*1024*1024, open_timeout=5)
    mid = 0
    async def cmd(method, params=None, timeout=45):
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
    await asyncio.sleep(12)  # slow proxy
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(4)
    print("turnstile global:", await ev("typeof turnstile"))
    print("page:", (await ev("document.body.innerText.slice(0,150)")).replace("\n"," | ")[:120])
    for i in range(30):
        await asyncio.sleep(2)
        ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
        tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
        if i % 3 == 0:
            print(f"  [{i}] ts_len={len(ts)} iframe={tsf}")
        if len(ts) > 50:
            print("NATURAL SOLVE OK:", ts[:30], "...")
            return
    print("NOT SOLVED")

asyncio.run(main())

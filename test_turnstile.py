#!/usr/bin/env python3
"""Test natural Turnstile solve: real typing + long wait (repo's browser_init flow)."""
import asyncio, json, urllib.request, random, string, os
import websockets

EMAIL = os.getenv("GMAIL_BASE_EMAIL", "") + "+grok" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8)) + "@gmail.com"

async def main():
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=10*1024*1024, open_timeout=5)
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
    await asyncio.sleep(7)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    # real type into email field
    await ev("(() => { const i = document.querySelector('input[type=email]'); if(i){i.focus(); return true;} return false; })()")
    await asyncio.sleep(0.5)
    await cmd("Input.insertText", {"text": EMAIL})
    await asyncio.sleep(1)
    # real click Sign up
    box = await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Sign up'); if(!b) return null; const r = b.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()""")
    if box:
        x, y = int(box["x"]), int(box["y"])
        await cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await asyncio.sleep(0.3)
        await cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.2)
        await cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    print("EMAIL:", EMAIL)
    print("submitted, polling turnstile 90s...")
    for i in range(45):
        await asyncio.sleep(2)
        ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
        tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
        if i % 5 == 0 or len(ts) > 10:
            print(f"  [{i}] ts_len={len(ts)} iframe={tsf}")
        if len(ts) > 50:
            print("SOLVED:", ts[:40], "...")
            break
    else:
        print("NOT SOLVED")
        t = await ev("document.body.innerText.slice(0,400)")
        print("TXT:", t.replace("\n"," | ")[:300])

asyncio.run(main())

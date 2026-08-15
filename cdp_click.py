#!/usr/bin/env python3
"""Click Sign up with email, dump form state + screenshot."""
import asyncio, json, base64, urllib.request
import websockets

async def main():
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=50*1024*1024)
    mid = 0
    async def cmd(method, params=None):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("id") == mid:
                return msg.get("result", {})
    await cmd("Page.enable")
    await cmd("Runtime.enable")
    await cmd("Page.navigate", {"url": "https://accounts.x.ai/sign-up?redirect=grok-com"})
    await asyncio.sleep(7)
    # click Sign up with email
    await cmd("Runtime.evaluate", {"expression": """
        (() => {
            const btns = Array.from(document.querySelectorAll('button,[role=button]'));
            const b = btns.find(b => (b.innerText||'').trim() === 'Sign up with email');
            if (b) { b.click(); return true; }
            return false;
        })()
    """, "returnByValue": True})
    await asyncio.sleep(4)
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelectorAll('input').length", "returnByValue": True})
    print("INPUTS after click:", r.get("result", {}).get("value"))
    r = await cmd("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('input')).map(i=>({type:i.type,name:i.name,ph:i.placeholder,id:i.id}))", "returnByValue": True})
    print("FIELDS:", json.dumps(r.get("result", {}).get("value"), ensure_ascii=False))
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelector('[name=cf-turnstile-response]')?.value?.length || 0", "returnByValue": True})
    print("TS_RESPONSE_LEN:", r.get("result", {}).get("value"))
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelector('iframe[src*=turnstile]')!==null", "returnByValue": True})
    print("TURNSTILE_IFRAME:", r.get("result", {}).get("value"))
    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_signup2.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_signup2.png")

asyncio.run(main())

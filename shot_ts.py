#!/usr/bin/env python3
"""Screenshot current tab with turnstile widget."""
import asyncio, json, urllib.request, base64
import websockets

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5))
    tab = [t for t in tabs if t.get("type") == "page"][-1]
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
    # check widget presence
    print("widget:", await ev("!!document.querySelector('#ts-widget')"))
    print("iframe:", await ev("!!document.querySelector('#ts-widget iframe')"))
    print("token:", (await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''"))[:30])
    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    if shot.get("data"):
        with open("/tmp/grok_ts_state2.png", "wb") as f:
            f.write(base64.b64decode(shot["data"]))
        print("SHOT saved")

asyncio.run(main())

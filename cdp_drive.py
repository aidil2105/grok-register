#!/usr/bin/env python3
"""Minimal CDP client to drive the debug Chrome on :9222."""
import asyncio, json, base64, sys, urllib.request
import websockets

WS = None
MSG_ID = 0
PENDING = {}

async def connect():
    global WS
    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
    WS = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=50*1024*1024)

async def cmd(method, params=None):
    global MSG_ID
    MSG_ID += 1
    mid = MSG_ID
    await WS.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await WS.recv())
        if msg.get("id") == mid:
            return msg.get("result", {})

async def main():
    await connect()
    await cmd("Page.enable")
    await cmd("Runtime.enable")
    await cmd("Page.navigate", {"url": "https://accounts.x.ai/sign-up?redirect=grok-com"})
    await asyncio.sleep(8)
    r = await cmd("Runtime.evaluate", {"expression": "document.title", "returnByValue": True})
    print("TITLE:", r.get("result", {}).get("value"))
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelectorAll('input').length", "returnByValue": True})
    print("INPUTS:", r.get("result", {}).get("value"))
    r = await cmd("Runtime.evaluate", {"expression": "Array.from(document.querySelectorAll('button,[role=button]')).map(b=>b.innerText.trim()).filter(t=>t.length<60)", "returnByValue": True})
    print("BUTTONS:", json.dumps(r.get("result", {}).get("value"), ensure_ascii=False)[:800])
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelector('iframe[src*=turnstile]')!==null || document.querySelector('iframe[src*=challenges]')!==null", "returnByValue": True})
    print("TURNSTILE_IFRAME:", r.get("result", {}).get("value"))
    r = await cmd("Runtime.evaluate", {"expression": "document.querySelector('[name=cf-turnstile-response]')?.value?.length || 0", "returnByValue": True})
    print("TS_RESPONSE_LEN:", r.get("result", {}).get("value"))
    # screenshot
    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_signup.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_signup.png")

asyncio.run(main())

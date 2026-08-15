#!/usr/bin/env python3
"""Probe F4E6D192 tab state robustly."""
import asyncio, json, urllib.request
import websockets

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5))
    tab = [t for t in tabs if t.get("type") == "page" and t["id"].startswith("F4E6D192")]
    if not tab:
        print("tab gone")
        return
    ws = await websockets.connect(tab[0]["webSocketDebuggerUrl"], max_size=10*1024*1024, open_timeout=5)
    mid = 0
    async def cmd(method, params=None, timeout=20):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if msg.get("id") == mid:
                return msg
    r = await cmd("Runtime.evaluate", {"expression": """
        JSON.stringify({
            url: location.href,
            hasTsIframe: !!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]'),
            tsResp: (document.querySelector('[name=cf-turnstile-response]')||{}).value || '',
            inputs: Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null).map(i=>({t:i.type,v:i.value.slice(0,3)})),
            errText: (document.body.innerText.match(/[^\\n]*(error|invalid|required|problem)[^\\n]*/gi)||[]).slice(0,3)
        })
    """, "returnByValue": True})
    val = r.get("result", {}).get("result", {}).get("value")
    print(val)

asyncio.run(main())

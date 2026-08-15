#!/usr/bin/env python3
"""Click Complete sign up and watch for network/page changes."""
import asyncio, json, urllib.request
import websockets

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5))
    tab = [t for t in tabs if t.get("type") == "page" and t["id"].startswith("F4E6D192")][0]
    ws = await websockets.connect(tab[0]["webSocketDebuggerUrl"] if False else tab["webSocketDebuggerUrl"], max_size=10*1024*1024, open_timeout=5)
    mid = 0
    events = []
    async def cmd(method, params=None, timeout=20):
        nonlocal mid
        mid += 1
        await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            if msg.get("id") == mid:
                return msg
    # enable network
    await cmd("Network.enable")
    await cmd("Page.enable")
    # click the complete button
    r = await cmd("Runtime.evaluate", {"expression": """
        (() => {
            const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Complete sign up');
            if(b){ b.click(); return 'clicked:' + b.disabled; }
            return 'not-found';
        })()
    """, "returnByValue": True})
    print("CLICK:", r.get("result", {}).get("result", {}).get("value"))
    # wait and collect network events
    for _ in range(12):
        try:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            if msg.get("method") in ("Network.requestWillBeSent", "Network.responseReceived", "Page.frameNavigated"):
                p = msg.get("params", {})
                if msg["method"] == "Network.requestWillBeSent":
                    events.append("REQ " + str(p.get("request", {}).get("url", ""))[:120])
                elif msg["method"] == "Network.responseReceived":
                    events.append("RES " + str(p.get("response", {}).get("status")) + " " + str(p.get("response", {}).get("url", ""))[:100])
                else:
                    events.append("NAV " + str(p.get("frame", {}).get("url", ""))[:120])
        except asyncio.TimeoutError:
            pass
    print("EVENTS:")
    for e in events[-15:]:
        print(" ", e)
    # check state after
    r = await cmd("Runtime.evaluate", {"expression": "location.href", "returnByValue": True})
    print("URL:", r.get("result", {}).get("result", {}).get("value"))
    r = await cmd("Runtime.evaluate", {"expression": "document.body.innerText.slice(0,300)", "returnByValue": True})
    print("TXT:", r.get("result", {}).get("result", {}).get("value", "").replace("\n", " | ")[:250])

asyncio.run(main())

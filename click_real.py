#!/usr/bin/env python3
"""Real mouse click on Complete sign up via CDP Input domain."""
import asyncio, json, urllib.request
import websockets

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=5))
    tab = [t for t in tabs if t.get("type") == "page" and t["id"].startswith("F4E6D192")][0]
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=10*1024*1024, open_timeout=5)
    mid = 0
    async def cmd(method, params=None, timeout=25):
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

    await cmd("Runtime.enable")
    # get button bounding box
    box = await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Complete sign up'); if(!b) return null; const r = b.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2, w: r.width, h: r.height}; })()""")
    print("BOX:", box)
    if not box:
        return
    x, y = int(box["x"]), int(box["y"])
    # real mouse click
    await cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
    await asyncio.sleep(0.3)
    await cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
    await asyncio.sleep(0.2)
    await cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    print("real click done, waiting...")
    await asyncio.sleep(6)
    u = await ev("location.href")
    t = await ev("document.body.innerText.slice(0,500)")
    print("URL:", u)
    print("TXT:", t.replace("\n"," | ")[:350])
    # turnstile?
    ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
    tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
    print("ts_len:", len(ts), "iframe:", tsf)

asyncio.run(main())

#!/usr/bin/env python3
"""Fill fields with REAL keyboard input via CDP, then real click."""
import asyncio, json, urllib.request, random, string
import websockets

PASSWORD = "".join(random.choices(string.ascii_lowercase + string.digits, k=14)) + "Aa1!"
first = "A" + "".join(random.choices(string.ascii_lowercase, k=4))
last = "B" + "".join(random.choices(string.ascii_lowercase, k=4))

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

    # focus first name input, select all, type real text
    async def type_into(index_expr, text):
        # focus via JS
        await ev(f"(() => {{ const vis = Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null); const i = {index_expr}; i.focus(); return true; }})()")
        await asyncio.sleep(0.3)
        # clear existing
        await cmd("Input.dispatchKeyEvent", {"type": "keyDown", "key": "a", "code": "KeyA", "modifiers": 2})
        await cmd("Input.dispatchKeyEvent", {"type": "keyUp", "key": "a", "code": "KeyA", "modifiers": 2})
        await cmd("Input.insertText", {"text": text})
        await asyncio.sleep(0.3)

    vis = await ev("Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null).map(i=>i.type)")
    print("visible inputs:", vis)

    # first name = first visible text input, last name = second
    text_inputs = [i for i, t in enumerate(vis) if t == "text"]
    pw_idx = vis.index("password") if "password" in vis else -1
    print("text idx:", text_inputs, "pw idx:", pw_idx)
    if len(text_inputs) >= 2:
        await type_into(f"Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null)[{text_inputs[0]}]", first)
        await type_into(f"Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null)[{text_inputs[1]}]", last)
    if pw_idx >= 0:
        await type_into(f"Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null)[{pw_idx}]", PASSWORD)
    print("PASSWORD:", PASSWORD)

    # check values now
    vals = await ev("Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null).map(i=>i.value)")
    print("VALUES:", vals)

    # real click on button
    box = await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Complete sign up'); if(!b) return null; const r = b.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()""")
    print("BOX:", box)
    if box:
        x, y = int(box["x"]), int(box["y"])
        await cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await asyncio.sleep(0.3)
        await cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.2)
        await cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    print("clicked, waiting...")
    await asyncio.sleep(8)
    u = await ev("location.href")
    t = await ev("document.body.innerText.slice(0,500)")
    print("URL:", u)
    print("TXT:", t.replace("\n"," | ")[:350])
    ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
    tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
    print("ts_len:", len(ts), "iframe:", tsf)
    # check for any error text
    errs = await ev("""(document.body.innerText.match(/[^\\n]*(error|invalid|required|problem|must)[^\\n]*/gi)||[]).slice(0,4)""")
    print("ERRS:", errs)

asyncio.run(main())

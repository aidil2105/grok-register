#!/usr/bin/env python3
"""Click complete, poll for turnstile render, then submit."""
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
    # click and poll for turnstile token/iframe
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Complete sign up'); if(b){b.click(); return true;} return false; })()""")
    print("clicked, polling turnstile...")
    for i in range(15):
        await asyncio.sleep(2)
        ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
        tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
        print(f"  [{i}] ts_len={len(ts)} iframe={tsf}")
        if len(ts) > 50:
            print("TURNSTILE SOLVED, submitting...")
            await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Complete sign up'); if(b){b.click(); return true;} return false; })()""")
            await asyncio.sleep(5)
            u = await ev("location.href")
            t = await ev("document.body.innerText.slice(0,400)")
            print("URL:", u)
            print("TXT:", t.replace("\n"," | ")[:300])
            break
    else:
        # try dispatching submit event on form
        r = await ev("""(() => { const f = document.querySelector('form'); if(f){ f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})); return 'form-submit'; } return 'no-form'; })()""")
        print("fallback:", r)
        await asyncio.sleep(5)
        u = await ev("location.href")
        t = await ev("document.body.innerText.slice(0,400)")
        print("URL:", u)
        print("TXT:", t.replace("\n"," | ")[:300])

asyncio.run(main())

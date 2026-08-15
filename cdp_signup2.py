#!/usr/bin/env python3
"""Continue signup: fill code, then name+password, submit, extract SSO."""
import asyncio, json, base64, urllib.request, re, random, string, sys, os
import websockets

CODE = os.getenv("XAI_SIGNUP_CODE", "")
EMAIL = os.getenv("XAI_SIGNUP_EMAIL", "")
PASSWORD = "".join(random.choices(string.ascii_lowercase + string.digits, k=14)) + "Aa1!"

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    tab = None
    for t in tabs:
        if t.get("type") == "page" and "accounts.x.ai" in t.get("url", ""):
            tab = t
            break
    if not tab:
        print("NO SIGNUP TAB FOUND")
        return
    print("TAB:", tab["url"])
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
    async def ev(expr):
        r = await cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        return r.get("result", {}).get("value")

    await cmd("Page.enable")
    await cmd("Runtime.enable")
    await cmd("Page.navigate", {"url": "https://accounts.x.ai/sign-up?redirect=grok-com"})
    await asyncio.sleep(6)
    # dismiss cookies, sign up with email
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    await ev(f"""(() => {{ const i = document.querySelector('input[type=email]'); if(i){{ const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; setter.call(i, '{EMAIL}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false; }})()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Sign up'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(4)
    # now on verify page, fill code
    filled = await ev(f"""(() => {{
        const inputs = document.querySelectorAll('input');
        for (const i of inputs) {{
            const vis = i.offsetParent !== null;
            const t = i.type;
            if (vis && (t==='text' || t==='tel' || t==='email')) {{
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                setter.call(i, '{CODE}');
                i.dispatchEvent(new Event('input',{{bubbles:true}}));
                i.dispatchEvent(new Event('change',{{bubbles:true}}));
                return true;
            }}
        }}
        return false;
    }})()""")
    print("code filled:", filled)
    await asyncio.sleep(1)
    # click Confirm email
    clicked = await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Confirm email'); if(b){b.click(); return true;} return false; })()""")
    print("confirm clicked:", clicked)
    await asyncio.sleep(5)
    t = await ev("document.body.innerText.slice(0, 800)")
    print("PAGE:", t.replace("\n", " | ")[:500])

    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_step3.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_step3.png")

asyncio.run(main())

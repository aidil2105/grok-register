#!/usr/bin/env python3
"""Fill code B1K-BAS into the open grokhbrrac8w tab and complete signup."""
import asyncio, json, base64, urllib.request, re, random, string
import websockets

CODE = "B1KBAS"
EMAIL = "awesomebeamy+grokhbrrac8w@gmail.com"
PASSWORD = "".join(random.choices(string.ascii_lowercase + string.digits, k=14)) + "Aa1!"
first = "A" + "".join(random.choices(string.ascii_lowercase, k=4))
last = "B" + "".join(random.choices(string.ascii_lowercase, k=4))

async def main():
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    tab = None
    for t in tabs:
        if t.get("type") == "page" and "accounts.x.ai" in t.get("url", ""):
            tab = t
            break
    if not tab:
        print("NO TAB"); return
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

    await cmd("Runtime.enable")
    await cmd("Page.enable")
    t = await ev("document.body.innerText.slice(0, 300)")
    print("CURRENT:", t.replace("\n", " | ")[:200])
    # check email shown on page
    shown = await ev("document.body.innerText.includes('grokhbrrac8w')")
    print("page shows grokhbrrac8w:", shown)

    # fill code
    fill = await ev(f"""(() => {{
        const vis = Array.from(document.querySelectorAll('input')).filter(i => i.offsetParent !== null);
        let target = vis.find(x => x.maxLength === 6 || x.getAttribute('maxlength') === '6');
        if (!target) target = vis.find(x => x.type === 'text' || x.type === 'tel');
        if (!target) return 'no-target';
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
        s.call(target, '{CODE}');
        target.dispatchEvent(new Event('input',{{bubbles:true}}));
        target.dispatchEvent(new Event('change',{{bubbles:true}}));
        return 'ok:' + target.value;
    }})()""")
    print("fill:", fill)
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Confirm email'); if(b){b.click(); return true;} return false; })()""")
    print("confirm clicked")

    advanced = False
    for _ in range(12):
        await asyncio.sleep(2)
        t = await ev("document.body.innerText.slice(0, 500)")
        if "first name" in t.lower() or "given name" in t.lower() or "password" in t.lower():
            advanced = True
            break
        if "invalid" in t.lower():
            print("ERR:", t.replace("\n", " | ")[:250])
            return
    print("advanced:", advanced)
    t = await ev("document.body.innerText.slice(0, 800)")
    print("PAGE:", t.replace("\n", " | ")[:450])

    await asyncio.sleep(1)
    nr = await ev(f"""(() => {{
        const vis = Array.from(document.querySelectorAll('input')).filter(i => i.offsetParent !== null);
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
        let n = 0;
        for (const i of vis) {{
            if (i.type === 'text' && n === 0) {{ s.call(i,'{first}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); n++; }}
            else if (i.type === 'text' && n === 1) {{ s.call(i,'{last}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); n++; }}
        }}
        return n;
    }})()""")
    print("names:", nr)
    pr = await ev(f"""(() => {{
        const i = Array.from(document.querySelectorAll('input')).find(x => x.offsetParent !== null && x.type === 'password');
        if(i){{ const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, '{PASSWORD}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false;
    }})()""")
    print("password:", pr)
    t = await ev("document.body.innerText.slice(0, 800)")
    print("PAGE2:", t.replace("\n", " | ")[:450])
    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_step6.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_step6.png")

asyncio.run(main())

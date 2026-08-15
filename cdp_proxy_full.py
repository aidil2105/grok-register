import os
#!/usr/bin/env python3
"""Full Grok signup via CDP through proxy. Real typing, Turnstile poll, SSO extract."""
import asyncio, json, base64, urllib.request, re, random, string, sys, time, imaplib, email as email_mod
import websockets

GMAIL_BASE = os.getenv("GMAIL_BASE_EMAIL", "")
GMAIL_PW = os.getenv("GMAIL_APP_PASSWORD", "")

def make_alias():
    tag = "grok" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{GMAIL_BASE.split('@')[0]}+{tag}@{GMAIL_BASE.split('@')[1]}"

def gmail_conn():
    c = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    c.login(GMAIL_BASE, GMAIL_PW)
    c.select("INBOX")
    return c

def last_uid(c):
    _, d = c.uid("SEARCH", None, "ALL")
    u = d[0].split()
    return int(u[-1]) if u else 0

def wait_code_for_alias(c, base_uid, alias, timeout=150):
    dl = time.time() + timeout
    prefix = alias.split("@")[0]
    while time.time() < dl:
        _, d = c.uid("SEARCH", None, f'(FROM "x.ai" UID {base_uid + 1}:*)')
        u = d[0].split()
        if u:
            for uid in u[-4:]:
                _, md = c.uid("FETCH", uid, "(BODY.PEEK[])")
                msg = email_mod.message_from_bytes(md[0][1])
                to_all = str(msg.get("To") or "") + " " + str(msg.get("Delivered-To") or "")
                if prefix in to_all or alias in to_all:
                    subj = str(msg.get("Subject") or "")
                    m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", subj)
                    if m:
                        return m.group(1) + m.group(2)
        time.sleep(4)
    return None

async def main():
    email_addr = make_alias()
    password = "".join(random.choices(string.ascii_lowercase + string.digits, k=14)) + "Aa1!"
    first = "A" + "".join(random.choices(string.ascii_lowercase, k=4))
    last = "B" + "".join(random.choices(string.ascii_lowercase, k=4))
    print("ALIAS:", email_addr)

    c = gmail_conn()
    base_uid = last_uid(c)

    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
    ws = await websockets.connect(tab["webSocketDebuggerUrl"], max_size=20*1024*1024, open_timeout=5)
    mid = 0
    async def cmd(method, params=None, timeout=30):
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
    async def click_text(text):
        return await ev(f"""(() => {{ const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='{text}'); if(b){{ b.click(); return true; }} return false; }})()""")
    async def type_into(selector, text):
        await ev(f"(() => {{ const i = document.querySelector('{selector}'); if(i){{ i.focus(); i.select(); return true; }} return false; }})()")
        await asyncio.sleep(0.4)
        await cmd("Input.insertText", {"text": text})
        await asyncio.sleep(0.3)

    await cmd("Page.enable")
    await cmd("Runtime.enable")
    await cmd("Page.navigate", {"url": "https://accounts.x.ai/sign-up?redirect=grok-com"})
    await asyncio.sleep(8)

    await click_text("Reject All")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    await type_into("input[type=email]", email_addr)
    await click_text("Sign up")
    print("email submitted, waiting code...")
    code = wait_code_for_alias(c, base_uid, email_addr)
    print("CODE:", code)
    if not code:
        print("FAIL: no code"); return

    await asyncio.sleep(2)
    # fill code with real typing into the visible code input
    await ev("""(() => { const vis = Array.from(document.querySelectorAll('input')).filter(i => i.offsetParent !== null); let t = vis.find(x => x.maxLength === 6 || x.getAttribute('maxlength') === '6'); if (!t) t = vis.find(x => x.type === 'text' || x.type === 'tel'); if (t) { t.focus(); return true; } return false; })()""")
    await asyncio.sleep(0.4)
    await cmd("Input.insertText", {"text": code})
    await asyncio.sleep(1)
    await click_text("Confirm email")
    print("confirm clicked")

    # wait for name/password page
    advanced = False
    for _ in range(15):
        await asyncio.sleep(2)
        t = await ev("document.body.innerText.slice(0, 500)")
        if "first name" in t.lower() or "given name" in t.lower() or "password" in t.lower():
            advanced = True; break
        if "invalid" in t.lower() or "expired" in t.lower():
            print("ERR:", t.replace("\n", " | ")[:250]); return
    print("advanced:", advanced)

    # fill names + password via real typing
    await asyncio.sleep(1)
    vis = await ev("Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null).map(i=>i.type)")
    print("inputs:", vis)
    ti = [i for i, t in enumerate(vis) if t == "text"]
    pi = vis.index("password") if "password" in vis else -1
    for idx, val in zip(ti, [first, last]):
        await ev(f"(() => {{ const vis = Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null); const i = vis[{idx}]; i.focus(); return true; }})()")
        await asyncio.sleep(0.3)
        await cmd("Input.insertText", {"text": val})
        await asyncio.sleep(0.3)
    if pi >= 0:
        await ev(f"(() => {{ const vis = Array.from(document.querySelectorAll('input')).filter(i=>i.offsetParent!==null); const i = vis[{pi}]; i.focus(); return true; }})()")
        await asyncio.sleep(0.3)
        await cmd("Input.insertText", {"text": password})
    print("PASSWORD:", password)
    print("fields filled")

    # check turnstile presence, click complete
    ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
    tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
    print("ts before submit:", len(ts), "iframe:", tsf)

    # real click Complete sign up
    box = await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Complete sign up'); if(!b) return null; const r = b.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; })()""")
    if box:
        x, y = int(box["x"]), int(box["y"])
        await cmd("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
        await asyncio.sleep(0.3)
        await cmd("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1})
        await asyncio.sleep(0.2)
        await cmd("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1})
    print("complete clicked, waiting...")
    await asyncio.sleep(8)
    u = await ev("location.href")
    t = await ev("document.body.innerText.slice(0, 500)")
    print("URL:", u)
    print("TXT:", t.replace("\n", " | ")[:300])
    ts = await ev("(document.querySelector('[name=cf-turnstile-response]')||{}).value || ''")
    tsf = await ev("!!document.querySelector('iframe[src*=turnstile],iframe[src*=challenges]')")
    print("ts after submit:", len(ts), "iframe:", tsf)

    # grab SSO cookie
    cookies = await cmd("Network.getAllCookies")
    sso = None
    for ck in cookies.get("cookies", []):
        if ck.get("name") == "sso":
            sso = ck.get("value")
            print("SSO domain:", ck.get("domain"))
    if sso:
        os.makedirs("/root/grok-register/keys", exist_ok=True)
        with open("/root/grok-register/keys/grok.txt", "a") as f:
            f.write(sso + "\n")
        with open("/root/grok-register/keys/accounts.txt", "a") as f:
            f.write(f"{email_addr}:{password}:{sso}\n")
        print("SSO SAVED:", sso[:40], "...")
    else:
        print("NO SSO")

asyncio.run(main())

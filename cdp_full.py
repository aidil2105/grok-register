import os
#!/usr/bin/env python3
"""Complete Grok signup in one shot via CDP. Outputs SSO cookie."""
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

def wait_code(c, base_uid, timeout=90):
    dl = time.time() + timeout
    while time.time() < dl:
        _, d = c.uid("SEARCH", None, f'(FROM "x.ai" UID {base_uid + 1}:*)')
        u = d[0].split()
        if u:
            _, md = c.uid("FETCH", u[-1], "(BODY.PEEK[])")
            msg = email_mod.message_from_bytes(md[0][1])
            subj = str(msg.get("Subject") or "")
            m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", subj)
            if m:
                return m.group(1) + m.group(2)
        time.sleep(4)
    return None

async def main():
    email_addr = make_alias()
    password = "".join(random.choices(string.ascii_lowercase + string.digits, k=14)) + "Aa1!"
    first = "".join(random.choices(string.ascii_uppercase, k=1)) + "".join(random.choices(string.ascii_lowercase, k=4))
    last = "".join(random.choices(string.ascii_uppercase, k=1)) + "".join(random.choices(string.ascii_lowercase, k=4))
    print("ALIAS:", email_addr)

    c = gmail_conn()
    base_uid = last_uid(c)

    req = urllib.request.Request("http://127.0.0.1:9222/json/new?about:blank", method="PUT")
    tab = json.load(urllib.request.urlopen(req, timeout=5))
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
    await asyncio.sleep(7)

    # dismiss cookies + email signup
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    # fill email
    await ev(f"""(() => {{ const i = document.querySelector('input[type=email]'); if(i){{ const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, '{email_addr}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false; }})()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Sign up'); if(b){b.click(); return true;} return false; })()""")
    print("email submitted, waiting code...")
    code = wait_code(c, base_uid)
    print("CODE:", code)
    if not code:
        print("FAIL: no code")
        return

    await asyncio.sleep(2)
    # fill code into the VISIBLE text input (max 6)
    filled = await ev(f"""(() => {{
        const inputs = Array.from(document.querySelectorAll('input')).filter(i => i.offsetParent !== null);
        const i = inputs.find(x => x.type === 'text' || x.type === 'tel');
        if(i){{ const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, '{code}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false;
    }})()""")
    print("code filled:", filled)
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Confirm email'); if(b){b.click(); return true;} return false; })()""")
    print("confirm clicked")
    await asyncio.sleep(5)
    t = await ev("document.body.innerText.slice(0, 500)")
    print("PAGE-A:", t.replace("\n", " | ")[:350])

    # Name + password step
    filled_name = await ev(f"""(() => {{
        const inputs = Array.from(document.querySelectorAll('input')).filter(i => i.offsetParent !== null);
        let count = 0;
        for (const i of inputs) {{
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
            if (i.type === 'text' && count === 0) {{ s.call(i, '{first}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); count++; }}
            else if (i.type === 'text' && count === 1) {{ s.call(i, '{last}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); count++; }}
        }}
        return count;
    }})()""")
    print("name fields filled:", filled_name)
    filled_pw = await ev(f"""(() => {{
        const i = Array.from(document.querySelectorAll('input')).find(x => x.offsetParent !== null && (x.type === 'password'));
        if(i){{ const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, '{password}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false;
    }})()""")
    print("password filled:", filled_pw)
    t = await ev("document.body.innerText.slice(0, 800)")
    print("PAGE-B:", t.replace("\n", " | ")[:450])

    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_step4.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_step4.png")

asyncio.run(main())

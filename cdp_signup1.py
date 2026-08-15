import os
#!/usr/bin/env python3
"""Full Grok signup via CDP: Gmail alias -> code -> password -> SSO cookie."""
import asyncio, json, base64, urllib.request, re, random, string, sys, os, time, imaplib, email as email_mod
import websockets

GMAIL_BASE = os.getenv("GMAIL_BASE_EMAIL", "")
GMAIL_PW = os.getenv("GMAIL_APP_PASSWORD", "")

def make_alias():
    tag = "grok" + "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{GMAIL_BASE.split('@')[0]}+{tag}@{GMAIL_BASE.split('@')[1]}"

def gmail_connect():
    c = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    c.login(GMAIL_BASE, GMAIL_PW)
    c.select("INBOX")
    return c

def get_last_uid(c):
    _, data = c.uid("SEARCH", None, "ALL")
    uids = data[0].split()
    return int(uids[-1]) if uids else 0

def wait_for_code(c, from_uid, to_addr, timeout=120):
    """Poll IMAP for x.ai mail to to_addr, return 6-char code."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, data = c.uid("SEARCH", None, f'(FROM "x.ai" UID {from_uid + 1}:*)')
        uids = data[0].split()
        if uids:
            for uid in uids[-3:]:
                _, msg_data = c.uid("FETCH", uid, "(BODY.PEEK[])")
                raw = msg_data[0][1]
                msg = email_mod.message_from_bytes(raw)
                # only the alias target
                all_to = (msg.get("To") or "") + (msg.get("Delivered-To") or "")
                if to_addr.split("@")[0] in all_to.replace("+", "+") or to_addr in all_to:
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() in ("text/plain", "text/html"):
                                p = part.get_payload(decode=True)
                                if p:
                                    body += p.decode("utf-8", "replace") + "\n"
                    else:
                        p = msg.get_payload(decode=True)
                        if p:
                            body = p.decode("utf-8", "replace")
                    m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", body)
                    if m:
                        return m.group(1) + m.group(2)
        time.sleep(5)
    return None

async def main():
    email_addr = make_alias()
    print("ALIAS:", email_addr)
    c = gmail_connect()
    base_uid = get_last_uid(c)

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

    # dismiss cookie banner
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    # click sign up with email
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    # fill email
    await ev(f"""(() => {{ const i = document.querySelector('input[type=email]'); if(i){{ const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; setter.call(i, '{email_addr}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false; }})()""")
    await asyncio.sleep(1)
    # click Sign up button
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Sign up'); if(b){b.click(); return true;} return false; })()""")
    print("submitted email, waiting for code...")
    await asyncio.sleep(3)
    # check page state
    t = await ev("document.body.innerText.slice(0, 500)")
    print("PAGE:", t.replace("\n", " | ")[:400])

    code = wait_for_code(c, base_uid, email_addr)
    print("CODE:", code)
    if not code:
        print("NO CODE RECEIVED")
        return

    # fill code input (likely a 6-digit code, maybe split inputs)
    await asyncio.sleep(2)
    code_inputs = await ev("document.querySelectorAll('input').length")
    print("inputs now:", code_inputs)
    # try single input first
    filled = await ev(f"""(() => {{
        const inputs = document.querySelectorAll('input');
        // find visible text input
        for (const i of inputs) {{
            if (i.type === 'text' || i.type === 'tel' || i.type === 'email') {{
                if (i.offsetParent !== null) {{
                    const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
                    setter.call(i, '{code}');
                    i.dispatchEvent(new Event('input',{{bubbles:true}}));
                    i.dispatchEvent(new Event('change',{{bubbles:true}}));
                    return true;
                }}
            }}
        }}
        return false;
    }})()""")
    print("code filled:", filled)
    await asyncio.sleep(1)
    t = await ev("document.body.innerText.slice(0, 600)")
    print("PAGE2:", t.replace("\n", " | ")[:400])

    # screenshot for state
    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_step2.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_step2.png")

asyncio.run(main())

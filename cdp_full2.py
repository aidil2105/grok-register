import os
#!/usr/bin/env python3
"""Complete Grok signup v2: correct alias matching + segmented code + wait for advance."""
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

def wait_code_for_alias(c, base_uid, alias, timeout=120):
    """Wait for x.ai email addressed to this exact alias, return 6-char code."""
    dl = time.time() + timeout
    prefix = alias.split("@")[0]
    while time.time() < dl:
        _, d = c.uid("SEARCH", None, f'(FROM "x.ai" UID {base_uid + 1}:*)')
        u = d[0].split()
        if u:
            for uid in u[-4:]:
                _, md = c.uid("FETCH", uid, "(BODY.PEEK[])")
                msg = email_mod.message_from_bytes(md[0][1])
                to_all = (str(msg.get("To") or "") + " " + str(msg.get("Delivered-To") or "") + " " + str(msg.get("X-Original-To") or ""))
                if prefix in to_all.replace("+", "+") or alias in to_all:
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

    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Reject All'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button,[role=button]')).find(b => (b.innerText||'').trim()==='Sign up with email'); if(b){b.click(); return true;} return false; })()""")
    await asyncio.sleep(3)
    await ev(f"""(() => {{ const i = document.querySelector('input[type=email]'); if(i){{ const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, '{email_addr}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false; }})()""")
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Sign up'); if(b){b.click(); return true;} return false; })()""")
    print("email submitted, waiting code...")
    code = wait_code_for_alias(c, base_uid, email_addr)
    print("CODE:", code)
    if not code:
        print("FAIL: no code")
        return

    await asyncio.sleep(2)
    # segmented code input: find all visible inputs; the code field is typically 6 char boxes
    # but our earlier probe showed a single input max=6 with segmented UI. Fill via keyboard events per segment.
    # Strategy: focus first segment, set value, dispatch input. Use the real input element.
    fill_res = await ev(f"""(() => {{
        const vis = Array.from(document.querySelectorAll('input')).filter(i => i.offsetParent !== null);
        // look for input with maxlength 6 or the field containing 'code'
        let target = vis.find(x => x.maxLength === 6 || x.getAttribute('maxlength') === '6');
        if (!target) target = vis.find(x => x.type === 'text' || x.type === 'tel');
        if (!target) return 'no-target';
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;
        s.call(target, '{code}');
        target.dispatchEvent(new Event('input',{{bubbles:true}}));
        target.dispatchEvent(new Event('change',{{bubbles:true}}));
        target.dispatchEvent(new KeyboardEvent('keyup',{{bubbles:true}}));
        return 'ok:' + target.value;
    }})()""")
    print("fill:", fill_res)
    await asyncio.sleep(1)
    await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Confirm email'); if(b){b.click(); return true;} return false; })()""")
    print("confirm clicked, waiting for advance...")

    # wait until name/password step appears (input[type=password] visible) or error
    advanced = False
    for _ in range(15):
        await asyncio.sleep(2)
        t = await ev("document.body.innerText.slice(0, 500)")
        if "password" in t.lower() or "first name" in t.lower() or "given name" in t.lower():
            advanced = True
            break
        if "invalid" in t.lower() or "try again" in t.lower():
            print("PAGE-ERR:", t.replace("\n", " | ")[:300])
            return
    print("advanced:", advanced)
    t = await ev("document.body.innerText.slice(0, 800)")
    print("PAGE:", t.replace("\n", " | ")[:500])

    # fill name + password
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
    print("names filled:", nr)
    pr = await ev(f"""(() => {{
        const i = Array.from(document.querySelectorAll('input')).find(x => x.offsetParent !== null && x.type === 'password');
        if(i){{ const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; s.call(i, '{password}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false;
    }})()""")
    print("password filled:", pr)
    t = await ev("document.body.innerText.slice(0, 800)")
    print("PAGE2:", t.replace("\n", " | ")[:500])

    shot = await cmd("Page.captureScreenshot", {"format": "png"})
    with open("/tmp/grok_step5.png", "wb") as f:
        f.write(base64.b64decode(shot["data"]))
    print("SHOT: /tmp/grok_step5.png")

asyncio.run(main())

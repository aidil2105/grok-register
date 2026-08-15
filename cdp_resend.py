import os
#!/usr/bin/env python3
"""Resend code, grab fresh one, fill + confirm."""
import asyncio, json, urllib.request, re, imaplib, email as email_mod, time, os
import websockets

EMAIL = os.getenv("XAI_SIGNUP_EMAIL", "")

def gmail_last_uid():
    c = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    c.login(os.getenv("GMAIL_BASE_EMAIL", ""), os.getenv("GMAIL_APP_PASSWORD", ""))
    c.select("INBOX")
    _, data = c.uid("SEARCH", None, "(FROM \"x.ai\")")
    uids = data[0].split()
    c.logout()
    return int(uids[-1]) if uids else 0

def wait_new_code(from_uid, timeout=90):
    c = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    c.login(os.getenv("GMAIL_BASE_EMAIL", ""), os.getenv("GMAIL_APP_PASSWORD", ""))
    c.select("INBOX")
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, data = c.uid("SEARCH", None, f'(FROM "x.ai" UID {from_uid + 1}:*)')
        uids = data[0].split()
        if uids:
            _, md = c.uid("FETCH", uids[-1], "(BODY.PEEK[])")
            msg = email_mod.message_from_bytes(md[0][1])
            subj = str(msg.get("Subject") or "")
            m = re.search(r"([A-Z0-9]{3})-?([A-Z0-9]{3})", subj)
            if m:
                c.logout()
                return m.group(1) + m.group(2)
        time.sleep(4)
    c.logout()
    return None

async def main():
    base_uid = gmail_last_uid()
    tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
    tab = [t for t in tabs if t.get("type") == "page" and "accounts.x.ai" in t.get("url", "")][0]
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
    # look for resend button
    btns = await ev("Array.from(document.querySelectorAll('button')).map(b=>(b.innerText||'').trim()).filter(t=>t.length<40)")
    print("BTNS:", btns)
    # clear the invalid input first
    await ev("""(() => { const i = document.querySelector('input[type=text][maxlength="6"]'); if(i){ const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; setter.call(i,''); i.dispatchEvent(new Event('input',{bubbles:true})); return true;} return false; })()""")
    # click resend / "Send new code" style button
    clicked = await ev("""(() => { const btns = Array.from(document.querySelectorAll('button')); const b = btns.find(b => /(resend|send new|again|new code)/i.test((b.innerText||'').trim())); if(b){b.click(); return true;} return false; })()""")
    print("resend clicked:", clicked)
    if not clicked:
        # maybe it's a link
        clicked = await ev("""(() => { const a = Array.from(document.querySelectorAll('a,button')).find(x => /(resend|send new|again)/i.test((x.innerText||'').trim())); if(a){a.click(); return true;} return false; })()""")
        print("resend clicked (a/button):", clicked)
    print("waiting for fresh code...")
    code = wait_new_code(base_uid)
    print("FRESH CODE:", code)
    if not code:
        return
    await asyncio.sleep(1)
    filled = await ev(f"""(() => {{
        const i = document.querySelector('input[type=text][maxlength="6"]');
        if(i){{ const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; setter.call(i, '{code}'); i.dispatchEvent(new Event('input',{{bubbles:true}})); i.dispatchEvent(new Event('change',{{bubbles:true}})); return true; }} return false;
    }})()""")
    print("filled:", filled)
    await asyncio.sleep(1)
    clicked = await ev("""(() => { const b = Array.from(document.querySelectorAll('button')).find(b => (b.innerText||'').trim()==='Confirm email'); if(b){b.click(); return true;} return false; })()""")
    print("confirm clicked:", clicked)
    await asyncio.sleep(5)
    t = await ev("document.body.innerText.slice(0, 900)")
    print("PAGE:", t.replace("\n", " | ")[:600])

asyncio.run(main())

#!/usr/bin/env python3
"""
Personal Grok proxy: OpenAI-compatible /v1 on localhost.
Keeps OAuth tokens fresh from auths/*.json, proxies to cli-chat-proxy.grok.com.
Usage: uvicorn grok_proxy:app --port 8099
"""
import json, os, glob, time, threading, urllib.parse
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse, Response
import httpx

AUTH_DIR = "/root/grok-register/auths"
BASE = "https://cli-chat-proxy.grok.com/v1"
TOKEN_ENDPOINT = "https://auth.x.ai/oauth2/token"
CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
REDIRECT_URI = "http://127.0.0.1:56121/callback"
MY_KEY = os.getenv("GROK_PROXY_KEY", "grok-personal")

app = FastAPI()
client = httpx.Client(timeout=300)
lock = threading.Lock()
accounts = []


def load_accounts():
    global accounts
    accounts = []
    for fn in sorted(glob.glob(os.path.join(AUTH_DIR, "xai-*.json"))):
        try:
            with open(fn) as f:
                d = json.load(f)
            if d.get("access_token") and not d.get("disabled"):
                d["_path"] = fn
                accounts.append(d)
        except Exception:
            pass
    print(f"[grok-proxy] loaded {len(accounts)} accounts")


def refresh(acc):
    try:
        r = client.post(TOKEN_ENDPOINT, data={
            "grant_type": "refresh_token",
            "refresh_token": acc["refresh_token"],
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
        }, timeout=30)
        if r.status_code != 200:
            print(f"[grok-proxy] refresh failed {acc.get('email')}: {r.status_code}")
            return
        d = r.json()
        acc["access_token"] = d["access_token"]
        if d.get("refresh_token"):
            acc["refresh_token"] = d["refresh_token"]
        acc["expires_in"] = d.get("expires_in", 21600)
        acc["_ts"] = time.time()
        with open(acc["_path"], "w") as f:
            json.dump(acc, f, ensure_ascii=False, indent=2)
        print(f"[grok-proxy] refreshed {acc.get('email')}")
    except Exception as e:
        print(f"[grok-proxy] refresh error {acc.get('email')}: {e}")


def get_token():
    with lock:
        for acc in accounts:
            ts = acc.get("_ts", 0)
            exp = acc.get("expires_in", 21600)
            if time.time() - ts > exp - 300:  # refresh 5 min before expiry
                refresh(acc)
            return acc["access_token"], acc
        # first run: force refresh if _ts unset
        if accounts:
            refresh(accounts[0])
            return accounts[0]["access_token"], accounts[0]
    raise HTTPException(503, "no accounts")


@app.on_event("startup")
def _startup():
    load_accounts()
    if accounts:
        with lock:
            refresh(accounts[0]) if not accounts[0].get("_ts") else None


def _headers(acc):
    return {
        "Authorization": f"Bearer {acc['access_token']}",
        "Content-Type": "application/json",
        "X-XAI-Token-Auth": "xai-grok-cli",
        "x-grok-client-version": "0.2.93",
        "x-grok-client-identifier": "grok-shell",
    }


def _check_key(req: Request):
    auth = req.headers.get("Authorization", "")
    if auth != f"Bearer {MY_KEY}":
        raise HTTPException(401, "bad key")


@app.get("/v1/models")
def models(req: Request):
    _check_key(req)
    return {"object": "list", "data": [
        {"id": "grok-4.6", "object": "model", "owned_by": "xai"},
        {"id": "grok-4.5", "object": "model", "owned_by": "xai"},
        {"id": "grok-chat-fast", "object": "model", "owned_by": "xai"},
        {"id": "grok-imagine-image", "object": "model", "owned_by": "xai"},
    ]}


@app.post("/v1/chat/completions")
async def chat(req: Request):
    _check_key(req)
    body = await req.body()
    tok, acc = get_token()
    headers = _headers(acc)
    headers["Content-Length"] = str(len(body))
    # strip unknown fields that grok may reject
    try:
        j = json.loads(body)
    except Exception:
        j = None
    if j:
        j.pop("stream_options", None)
        j.pop("user", None)
        body = json.dumps(j).encode()
        headers["Content-Length"] = str(len(body))
    req_headers = dict(headers)
    upstream = client.build_request("POST", f"{BASE}/chat/completions", content=body, headers=req_headers)
    r = client.send(upstream, stream=True)
    if r.status_code != 200:
        return Response(content=r.read(), status_code=r.status_code, media_type="application/json")
    if j and j.get("stream"):
        return StreamingResponse(r.iter_raw(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})
    return Response(content=r.read(), media_type="application/json")


@app.post("/v1/images/generations")
async def image(req: Request):
    _check_key(req)
    body = await req.body()
    tok, acc = get_token()
    headers = _headers(acc)
    headers["Content-Length"] = str(len(body))
    upstream = client.build_request("POST", f"{BASE}/images/generations", content=body, headers=headers)
    r = client.send(upstream)
    return Response(content=r.content, status_code=r.status_code, media_type="application/json")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8099)

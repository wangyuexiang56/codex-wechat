from http.server import BaseHTTPRequestHandler
import os, time, hashlib, json, urllib.request, xml.etree.ElementTree as ET

API_KEY = os.environ.get("OPENAI_API_KEY", "")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
WX_TOKEN = os.environ.get("WX_TOKEN", "codex2024")

# Simple in-memory sessions (resets on cold start - acceptable for demo)
sessions = {}

def ask_codex(text, uid):
    if uid not in sessions:
        sessions[uid] = []
    h = sessions[uid]
    h.append({"role": "user", "content": text})
    if len(h) > 20:
        h = h[-20:]
    try:
        data = json.dumps({
            "model": MODEL,
            "messages": [{"role":"system","content":"你是 Codex, 友好的 AI 助手。用中文回复, 简洁准确。"}, *h],
            "temperature": 0.7,
            "max_tokens": 1500
        }).encode()
        req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=data,
            headers={"Content-Type":"application/json", "Authorization":f"Bearer {API_KEY}"})
        resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
        reply = resp["choices"][0]["message"]["content"]
        h.append({"role": "assistant", "content": reply})
        sessions[uid] = h
        return reply
    except Exception as e:
        return "抱歉, 请稍后重试。"

def parse_xml(data):
    root = ET.fromstring(data)
    return {c.tag: c.text or "" for c in root}

def build_reply(to_user, from_user, content):
    return f"""<xml>
<ToUserName><![CDATA[{to_user}]]></ToUserName>
<FromUserName><![CDATA[{from_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        q = parse_qs(urlparse(self.path).query)
        sig = q.get("signature", [""])[0]
        ts = q.get("timestamp", [""])[0]
        nonce = q.get("nonce", [""])[0]
        echo = q.get("echostr", [""])[0]
        tmp = "".join(sorted([WX_TOKEN, ts, nonce]))
        h = hashlib.sha1(tmp.encode()).hexdigest()
        if h == sig:
            self.send_response(200)
            self.end_headers()
            self.wfile.write(echo.encode())
            return
        self.send_response(403)
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        msg = parse_xml(body)
        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")

        reply = ""
        if msg.get("MsgType") == "text":
            text = msg.get("Content", "").strip()
            reply = ask_codex(text, from_user)
        elif msg.get("Event") == "subscribe":
            reply = "你好! 我是 Codex AI 助手。\n直接发消息就能和我聊天。"

        if reply:
            xml = build_reply(from_user, to_user, reply)
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.end_headers()
            self.wfile.write(xml.encode())
            return
        self.send_response(200)
        self.end_headers()

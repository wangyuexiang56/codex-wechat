# -*- coding: utf-8 -*-
"""微信公众号 Codex 机器人 - 好友式聊天
部署后，在微信里像好友一样直接对话。
"""

import os, time, hashlib, json
from flask import Flask, request, Response
from openai import OpenAI
import xml.etree.ElementTree as ET

# ========== 配置 ==========
API_KEY  = os.environ.get("OPENAI_API_KEY", "")
API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
MODEL    = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
PORT     = int(os.environ.get("PORT", "10000"))
WX_TOKEN = os.environ.get("WX_TOKEN", "codex2024")

app = Flask(__name__)
client = OpenAI(api_key=API_KEY, base_url=API_BASE)

# ========== 对话记忆 ==========
sessions = {}

def ask_codex(text, uid):
    if uid not in sessions:
        sessions[uid] = []
    h = sessions[uid]
    h.append({"role": "user", "content": text})
    if len(h) > 30:
        h = h[-30:]
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role":"system","content":"你是 Codex, 友好的 AI 助手。用中文回复, 简洁准确。"}, *h],
            temperature=0.7, max_tokens=1500
        )
        reply = resp.choices[0].message.content
        h.append({"role": "assistant", "content": reply})
        sessions[uid] = h
        return reply
    except Exception as e:
        return f"出错了: {e}"

# ========== 微信消息处理 ==========
def parse_wx_msg(xml_data):
    """解析微信 XML 消息"""
    root = ET.fromstring(xml_data)
    msg = {}
    for child in root:
        msg[child.tag] = child.text or ""
    return msg

def build_wx_reply(to_user, from_user, content):
    """构建微信 XML 回复"""
    tmpl = """<xml>
<ToUserName><![CDATA[{to}]]></ToUserName>
<FromUserName><![CDATA[{from_}]]></FromUserName>
<CreateTime>{time}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
    return tmpl.format(
        to=to_user, from_=from_user,
        time=int(time.time()), content=content
    )

@app.route("/wx", methods=["GET", "POST"])
def wechat():
    if request.method == "GET":
        # 微信验证
        signature = request.args.get("signature", "")
        timestamp = request.args.get("timestamp", "")
        nonce = request.args.get("nonce", "")
        echostr = request.args.get("echostr", "")

        tmp = sorted([WX_TOKEN, timestamp, nonce])
        tmp_str = "".join(tmp)
        if hashlib.sha1(tmp_str.encode()).hexdigest() == signature:
            return echostr
        return "fail"

    # POST: 接收消息
    xml_data = request.data
    msg = parse_wx_msg(xml_data)
    msg_type = msg.get("MsgType", "")
    from_user = msg.get("FromUserName", "")
    to_user = msg.get("ToUserName", "")

    if msg_type == "text":
        text = msg.get("Content", "").strip()
        print(f"[微信] {from_user[:12]}...: {text[:60]}")

        reply = ask_codex(text, from_user)
        xml_reply = build_wx_reply(from_user, to_user, reply)
        return Response(xml_reply, content_type="application/xml")

    elif msg_type == "event":
        event = msg.get("Event", "")
        if event == "subscribe":
            welcome = "你好！我是 Codex AI 助手 \n\n直接发消息就能和我聊天。"
            return Response(
                build_wx_reply(from_user, to_user, welcome),
                content_type="application/xml"
            )
        elif event == "unsubscribe":
            sessions.pop(from_user, None)

    return ""

@app.route("/health")
def health():
    return "OK"

# ========== 启动 ==========
if __name__ == "__main__":
    print(f"启动公众号服务器, 端口 {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False)

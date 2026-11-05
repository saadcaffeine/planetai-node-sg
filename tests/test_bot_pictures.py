"""Pictures sent to the bot (Tomas, 15 Oct 2026): a household's photo or image file goes to the node's POST /captures,
a stranger's goes nowhere, and the bot token never reaches a log line or a reply.

The functions are lifted out of app/agent_loop.py by AST (importing it starts the bot), with Telegram, its file
server and the node faked. Nothing here talks to the network.

Run: PYTHONPATH=app python3 tests/test_bot_pictures.py
"""
import ast
import asyncio
import logging
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = (ROOT / "app" / "agent_loop.py").read_text()
TOKEN = "123456:SECRET-bot-token"

# ---------------------------------------------------------------- fakes: Telegram, its file server, the node
FILES = {"small": b"tiny", "big": b"\xff\xd8 the big photo", "mid": b"middle", "orig": b"\x00EXIF GPS 41.39N 2.16E raw",
         "boom": b""}
SENT, GETFILE, POSTS = [], [], []


async def telegram(method, **p):
    if method == "getFile":
        GETFILE.append(p["file_id"])
        return {"ok": True, "result": {"file_id": p["file_id"], "file_path": f"photos/{p['file_id']}.jpg"}}
    SENT.append((method, p))
    return {"ok": True}


class HTTPError(Exception):
    pass


class FakeHttpx:
    HTTPError = HTTPError

    class AsyncClient:
        def __init__(self, **kw): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False

        async def get(self, url):
            assert url.startswith(f"https://api.telegram.org/file/bot{TOKEN}/photos/"), url
            fid = url.rsplit("/", 1)[1][:-4]
            if fid == "boom":   # httpx's own messages quote the URL, and with it the token
                raise HTTPError(f"Server disconnected while reading {url}")
            return Resp(200, content=FILES[fid])


class Resp:
    def __init__(self, status_code, body=None, content=b""):
        self.status_code, self.body, self.content = status_code, body, content
    def json(self):
        if self.body is None:
            raise ValueError("not json")
        return self.body


NODE_ANSWER = [Resp(200, {"ok": True, "capture": {"id": 7}, "describing": True})]


class Node:
    async def post(self, url, files=None, data=None, timeout=None):
        POSTS.append({"url": url, "files": files, "data": data})
        return NODE_ANSWER[0]


class Logs(logging.Handler):
    lines = []
    def emit(self, record): self.lines.append(record.getMessage())


log = logging.getLogger("bot-pictures-test")
log.setLevel(logging.INFO)
log.addHandler(Logs())
log.propagate = False

ns = {"re": re, "telegram": telegram, "T": lambda en, **o: en, "CHATS": lambda: {"109"}, "TG_TOKEN": lambda: TOKEN,
      "node_url": lambda p: "http://app:8080" + p, "log": log, "httpx": FakeHttpx, "time": time}
WANT = {"TG_FILE_MAX", "PICTURE_KINDS", "picture_of", "kind_and_note", "tg_download", "keep_picture", "_name_of",
        "TelegramError"}
for node in ast.parse(SRC).body:
    targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
    names = {getattr(t, "id", None) for t in targets} | {getattr(node, "name", None)}
    if names & WANT:
        exec(compile(ast.Module([node], []), "agent_loop.py", "exec"), ns)
assert WANT <= set(ns), f"agent_loop.py lost {WANT - set(ns)}"


def send(m, chat="109"):
    SENT.clear(); GETFILE.clear(); POSTS.clear()
    return asyncio.run(ns["keep_picture"](Node(), m, chat))


def said():
    return [p["text"] for meth, p in SENT if meth == "sendMessage"]


ana = {"first_name": "Ana", "username": "ana_b"}

# ---------------------------------------------------------------- a photo from the household: the largest, kept
photo = {"message_id": 41, "date": 1760500000, "from": ana, "chat": {"id": 109}, "caption": "the fig tree by the gate",
         "photo": [{"file_id": "small", "width": 90, "height": 90, "file_size": 1200},
                   {"file_id": "big", "width": 1280, "height": 960, "file_size": 180000},
                   {"file_id": "mid", "width": 320, "height": 240, "file_size": 9000}]}
assert send(photo) is True
assert GETFILE == ["big"], "the largest size, by its pixels, not its place in the list"
assert len(POSTS) == 1 and POSTS[0]["url"] == "http://app:8080/captures", "one POST /captures"
name, raw, mime = POSTS[0]["files"]["photo"]
assert raw == FILES["big"] and mime == "image/jpeg"
d = POSTS[0]["data"]
assert d["kind"] == "phone" and d["note"] == "the fig tree by the gate" and d["actor"] == "Ana" and d["describe"] == "1"
assert d["taken_at"] == "2025-10-15T03:46:40+00:00", "a photo lost its own date to Telegram: the message's stands in"
assert said() == ["Kept. The image model on this machine is describing it; it will be in Data › Images in a minute."]
print("a household photo: its largest size, one POST /captures with the caption, the name and describe=1, and Kept")

# ---------------------------------------------------------------- a picture sent as a file: the original, byte for byte
doc = {"message_id": 42, "date": 1760500000, "from": ana, "chat": {"id": 109},
       "document": {"file_id": "orig", "file_name": "IMG_2041.HEIC", "mime_type": "image/heic", "file_size": 3_100_000}}
send(doc)
assert POSTS[0]["files"]["photo"] == ("IMG_2041.HEIC", FILES["orig"], "image/heic"), "the original's bytes, untouched"
assert "taken_at" not in POSTS[0]["data"], "the file's own date wins on the node, so the message's is not sent"
assert POSTS[0]["data"]["note"] == "" and POSTS[0]["data"]["kind"] == "phone"
print("an image sent as a file: the same bytes reach the node, its own EXIF date and GPS with them")

# ---------------------------------------------------------------- a caption tag names what took it
kn = ns["kind_and_note"]
assert kn("#drone over the dump") == ("drone", "over the dump")
assert kn("leaf #Microscope #mould") == ("microscope", "leaf #mould"), "only the five kinds are tags; the rest is the note"
assert kn("") == ("phone", "") and kn("#balloon") == ("balloon", "")
send(dict(photo, caption="#camera the yard at noon"))
assert POSTS[0]["data"]["kind"] == "camera" and POSTS[0]["data"]["note"] == "the yard at noon"
print("a caption's #drone, #microscope, #camera or #balloon sets the kind and leaves the note")

# ---------------------------------------------------------------- the node's other answers, in plain words
NODE_ANSWER[0] = Resp(200, {"ok": True, "duplicate": True, "capture": {"id": 7}})
send(photo)
assert said() == ["That picture is already kept."]
NODE_ANSWER[0] = Resp(200, {"ok": True, "capture": {"id": 8}, "describing": False})
send(photo)
assert said() == ["Kept. It is in Data › Images. No image model is set, so nothing describes it yet."], \
    "it does not promise a description nothing will write"
NODE_ANSWER[0] = Resp(415, {"detail": "a GIF is not a picture this node keeps (jpeg, png, heic or webp)"})
send(photo)
assert said() == ["The node did not keep it: a GIF is not a picture this node keeps (jpeg, png, heic or webp)"]
NODE_ANSWER[0] = Resp(401, {"detail": "the captures answer only this machine or Authorization: Bearer ***"})
send(photo)
assert said() == ["The node did not accept this picture. Whoever set up the node needs to check the bot's access."], \
    "the household is told who can fix it, never the token's name"
NODE_ANSWER[0] = Resp(502)
send(photo)
assert said() == ["The node did not keep it; send it again in a minute."], "an answer that is not JSON still gets a reply, with no status code"
NODE_ANSWER[0] = Resp(200, {"ok": True, "capture": {"id": 7}, "describing": True})
print("a duplicate, no image model, a refusal and a token the node refuses are each said plainly")

# ---------------------------------------------------------------- refusals before anything is fetched
assert send({**doc, "document": dict(doc["document"], file_size=21 * 1024 * 1024)}) is True
assert not GETFILE and not POSTS and "over 20 MB" in said()[0], "the Bot API's limit is said, and nothing is fetched"
send({**doc, "document": {"file_id": "orig", "file_name": "plan.pdf", "mime_type": "application/pdf"}})
assert not GETFILE and not POSTS and said()[0].startswith("I keep pictures only")
print("a file over 20 MB and a file that is not an image are refused with the reason, and nothing is fetched")

# ---------------------------------------------------------------- strangers upload nothing
assert send(photo, chat="555") is False
assert not GETFILE and not POSTS and not SENT, "a stranger's picture is ignored, as their words are"
assert send({**doc, "chat": {"id": 555}}, chat="555") is False and not POSTS
print("a stranger's photo or file: nothing fetched, nothing posted, nothing said")

# ---------------------------------------------------------------- the token never reaches a log line or a reply
Logs.lines.clear()
send({**photo, "photo": [{"file_id": "boom", "width": 9, "height": 9}]})
assert not POSTS and said()[0].startswith("⚠️ I could not fetch that picture"), "a failed download keeps nothing"
assert Logs.lines and not any("SECRET" in x or "api.telegram.org" in x for x in Logs.lines + said()), Logs.lines
for resp in (Resp(401, {"detail": "x"}), Resp(500, {"detail": "boom"})):
    NODE_ANSWER[0] = resp
    send(photo)
assert not any("SECRET" in x or "bot123456" in x for x in Logs.lines + said()), "no token in any log line"
print("a download that fails with the URL in its message logs the error's type, never the token")

# ---------------------------------------------------------------- the loop hands every picture to keep_picture first
loop = SRC[SRC.index("async def main():"):]
assert loop.index("if picture_of(m):") < loop.index("if not text:") < loop.index("if chat not in CHATS():"), \
    "a picture has no text: it must be routed before the text-only early exit and the stranger branch"
print("bot pictures: every check passed")
sys.exit(0)

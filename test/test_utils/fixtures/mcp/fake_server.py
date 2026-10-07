"""A small MCP server for the tests: the protocol on standard input and output, standard library only.

It offers a handful of tools that each do one thing a client has to cope with
(answer, take long, fail, refuse, leak a secret, go away, write noise), two
resources and a prompt. Options on the command line change how it behaves as a
whole:

``--protocol <version>``  answer the handshake with that protocol version
``--pages``               list the tools one a page
``--silent``              never answer the handshake
"""
import json
import os
import sys
import time

OPTIONS = sys.argv[1:]
PROTOCOL = OPTIONS[OPTIONS.index("--protocol") + 1] if "--protocol" in OPTIONS else None
PAGES = "--pages" in OPTIONS
SILENT = "--silent" in OPTIONS


def text_schema(*required):
    return {"type": "object", "properties": {name: {"type": "string"} for name in required},
            "required": list(required)}


TOOLS = [
    {"name": "echo", "description": "Give back the text it is given.", "inputSchema": text_schema("text"),
     "annotations": {"readOnlyHint": True, "title": "Echo"}},
    {"name": "write_file", "title": "Write a file", "description": "Write content to a path.",
     "inputSchema": text_schema("path", "content"), "annotations": {"destructiveHint": True}},
    {"name": "slow", "description": "Answer after some seconds.",
     "inputSchema": {"type": "object", "properties": {"seconds": {"type": "number"}}, "required": ["seconds"]}},
    {"name": "fail", "description": "Run and say it failed.", "inputSchema": {"type": "object"}},
    {"name": "refuse", "description": "Answer with a protocol error.", "inputSchema": {"type": "object"}},
    {"name": "leak", "description": "Print the token it was started with.", "inputSchema": {"type": "object"}},
    {"name": "quit", "description": "End without answering.", "inputSchema": {"type": "object"}},
    {"name": "noise", "description": "Write lines that are not messages, then answer.",
     "inputSchema": {"type": "object"}},
    {"name": "picture", "description": "Give back an image and a link.", "inputSchema": {"type": "object"}},
    {"name": "seen", "description": "Say what the client sent that was not a request.",
     "inputSchema": {"type": "object"}},
    {"name": "wrong_shape", "description": "Answer with a result that is not an object.",
     "inputSchema": {"type": "object"}},
]
RESOURCES = [
    {"uri": "memo://greeting", "name": "greeting", "description": "A greeting.", "mimeType": "text/plain"},
    {"uri": "memo://logo", "name": "logo", "mimeType": "image/png"},
]
PROMPTS = [{"name": "review", "description": "Ask for a review of some code.", "arguments": [
    {"name": "code", "description": "The code to review.", "required": True},
    {"name": "tone", "description": "How to say it."}]}]

# What the client sent that was not a request: cancellations, and its replies to this server's own requests
seen = {"cancelled": [], "replies": [], "notifications": []}


def send(message):
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def content(text):
    return {"content": [{"type": "text", "text": text}]}


def call(name, arguments, request_id):
    if name == "echo":
        return content(arguments.get("text", ""))
    if name == "write_file":
        return content("wrote " + arguments.get("path", ""))
    if name == "slow":
        time.sleep(float(arguments.get("seconds", 1)))
        return content("done")
    if name == "fail":
        return {"content": [{"type": "text", "text": "the disk is full\nno space left"}], "isError": True}
    if name == "refuse":
        send({"jsonrpc": "2.0", "id": request_id,
              "error": {"code": -32602, "message": "not with these arguments, token " + os.environ.get("FAKE_TOKEN", "")}})
        return None
    if name == "leak":
        token = os.environ.get("FAKE_TOKEN", "")
        sys.stderr.write("starting with token " + token + "\n")
        sys.stderr.flush()
        return {"content": [{"type": "text", "text": "my token is " + token}],
                "structuredContent": {"token": token, "note": "seen " + token}}
    if name == "quit":
        sys.exit(3)
    if name == "noise":
        sys.stdout.write("\nthis is not a message\n[1, 2]\n")
        sys.stdout.flush()
        return content("after the noise")
    if name == "picture":
        return {"content": [{"type": "image", "data": "aGVsbG8=", "mimeType": "image/png"},
                            {"type": "resource_link", "uri": "memo://logo"},
                            {"type": "resource", "resource": {"uri": "memo://greeting", "text": "hello"}}]}
    if name == "seen":
        return content(json.dumps(seen, sort_keys=True))
    if name == "wrong_shape":
        send({"jsonrpc": "2.0", "id": request_id, "result": "not an object"})
        return None
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "unknown tool " + name}})
    return None


def listed_tools(params):
    if not PAGES:
        return {"tools": TOOLS}
    at = int(params.get("cursor") or 0)
    page = {"tools": TOOLS[at:at + 1]}
    if at + 1 < len(TOOLS):
        page["nextCursor"] = str(at + 1)
    return page


def answer(method, params, request_id):
    if method == "initialize":
        if SILENT:
            return None
        return {"protocolVersion": PROTOCOL or params.get("protocolVersion"),
                "capabilities": {"tools": {"listChanged": True}, "resources": {}, "prompts": {}},
                "serverInfo": {"name": "fake-server", "version": "1.2.3"}, "instructions": "Be kind to the fake."}
    if method == "ping":
        return {}
    if method == "tools/list":
        return listed_tools(params)
    if method == "tools/call":
        return call(params.get("name"), params.get("arguments") or {}, request_id)
    if method == "resources/list":
        return {"resources": RESOURCES}
    if method == "resources/read":
        if params.get("uri") == "memo://greeting":
            return {"contents": [{"uri": "memo://greeting", "mimeType": "text/plain", "text": "hello there"}]}
        return {"contents": [{"uri": params.get("uri"), "mimeType": "image/png", "blob": "aGVsbG8="}]}
    if method == "prompts/list":
        return {"prompts": PROMPTS}
    if method == "prompts/get":
        given = params.get("arguments") or {}
        return {"description": "A review.", "messages": [
            {"role": "user", "content": {"type": "text", "text": "Please review: " + given.get("code", "")}},
            {"role": "assistant", "content": {"type": "text", "text": "In a " + given.get("tone", "plain") + " tone."}}]}
    send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "no such method " + method}})
    return None


for line in sys.stdin:
    if not line.strip():
        continue
    message = json.loads(line)
    method = message.get("method")
    if method is None:
        seen["replies"].append(message)
        continue
    if "id" not in message:
        if method == "notifications/cancelled":
            seen["cancelled"].append(message.get("params", {}).get("requestId"))
        else:
            seen["notifications"].append(method)
        if method == "notifications/initialized":
            # What a server may ask of a client: a ping, and something this client does not offer
            send({"jsonrpc": "2.0", "id": "server-1", "method": "ping"})
            send({"jsonrpc": "2.0", "id": "server-2", "method": "roots/list"})
            send({"jsonrpc": "2.0", "method": "notifications/message",
                  "params": {"level": "info", "data": "ready"}})
        continue
    result = answer(method, message.get("params") or {}, message["id"])
    if result is not None:
        send({"jsonrpc": "2.0", "id": message["id"], "result": result})

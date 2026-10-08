"""A minimal MCP server for the tutorial: two tools, on standard input and output, standard library only.

Run by an MCP client (PyBreeze's MCP Client tab), never by hand: it reads one
JSON message a line and answers the same way.

``now``  says the time, and changes nothing.
``add``  adds two numbers.
"""
import json
import sys
from datetime import datetime, timezone

TOOLS = [
    {
        "name": "now",
        "description": "The current time, in UTC.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"readOnlyHint": True},
    },
    {
        "name": "add",
        "description": "Add two numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
            "required": ["a", "b"],
        },
        "annotations": {"readOnlyHint": True},
    },
]


def call(name, arguments):
    """What the tool *name* gives for *arguments*, as the protocol's content."""
    if name == "now":
        text = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    elif name == "add":
        text = str(arguments["a"] + arguments["b"])
    else:
        return {"content": [{"type": "text", "text": "no such tool: " + str(name)}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


def answer(method, params):
    """The result of the request *method*, or ``None`` for one this server does not have."""
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "tutorial-time-server", "version": "1.0.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        return call(params.get("name"), params.get("arguments") or {})
    return None


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        message = json.loads(line)
        if "id" not in message:
            continue  # a notification: nothing to answer
        result = answer(message.get("method"), message.get("params") or {})
        reply = {"jsonrpc": "2.0", "id": message["id"]}
        if result is None:
            reply["error"] = {"code": -32601, "message": "no such method"}
        else:
            reply["result"] = result
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

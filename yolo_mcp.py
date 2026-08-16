#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yolo_mcp.py — 轻量 MCP (Model Context Protocol) stdio 服务器
向 Hermes Agent 暴露 `yolo_detect` 工具，底层调用 yolo_tool.py。

零第三方依赖（仅标准库），通信采用标准 MCP stdio framing：
  Content-Length: <N>\r\n\r\n<JSON body 字节流>
（与 Claude Desktop / Hermes 等 MCP 客户端一致）

注册方式（~/.config/hermes/.hermes/config.yaml）:
    mcp_servers:
      - name: yolo-mcp
        command: python3 /home/pi/hermes-yolo/yolo_mcp.py

注册后工具名为: yolo-mcp__yolo_detect
"""
import json
import os
import subprocess
import sys

# 协商后的协议版本（initialize 时由客户端请求确定）
# 决定响应用 newline-delimited JSON（2025+）还是 Content-Length framing（2024）
_NEGOTIATED_VERSION = "2024-11-05"

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
YOLO_TOOL = os.path.join(TOOL_DIR, "yolo_tool.py")

TOOLS = [
    {
        "name": "yolo_detect",
        "description": (
            "使用 YOLOv8n 模型检测图片中的物体，返回每个检测框的类别、置信度与边界框坐标。"
            "适合回答'图片里有什么'、'检测图片中的目标'等问题。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "image": {
                    "type": "string",
                    "description": "图片文件绝对路径（如 /home/pi/Desktop/test.jpg），或 camera:0 表示从摄像头捕获一帧",
                },
                "conf": {
                    "type": "number",
                    "description": "置信度阈值，默认 0.25",
                },
            },
            "required": ["image"],
        },
    }
]


def log(msg: str) -> None:
    """日志写入 stderr，避免污染 MCP stdout 协议流。"""
    sys.stderr.write(f"[yolo-mcp] {msg}\n")
    sys.stderr.flush()


def run_yolo(image: str, conf: float = 0.25) -> str:
    """调用 yolo_tool.py，返回 JSON 文本。"""
    cmd = [sys.executable, YOLO_TOOL, image, "--conf", str(conf)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if proc.returncode != 0:
        err = proc.stderr.strip() or proc.stdout.strip() or f"exit code {proc.returncode}"
        raise RuntimeError(f"yolo_tool.py 执行失败: {err}")
    return proc.stdout.strip()


def call_tool(name: str, arguments: dict) -> dict:
    """执行工具调用，返回 MCP content 格式。"""
    if name != "yolo_detect":
        return {"content": [{"type": "text", "text": f"未知工具: {name}"}], "isError": True}
    image = arguments.get("image", "")
    if not image:
        return {"content": [{"type": "text", "text": "缺少参数 image（图片路径）"}], "isError": True}
    conf = arguments.get("conf", 0.25)
    try:
        output = run_yolo(image, conf)
        return {"content": [{"type": "text", "text": output}]}
    except Exception as e:  # noqa: BLE001
        log(str(e))
        return {"content": [{"type": "text", "text": f"检测失败: {e}"}], "isError": True}


def handle(msg: dict) -> dict | None:
    """处理单个 JSON-RPC 消息；通知类消息返回 None。"""
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        # 协议版本协商：记录客户端请求的版本，后续响应按该版本格式输出。
        # mcp SDK 1.28+ 发送 LATEST_PROTOCOL_VERSION (2025-11-25)，
        # 且用 newline-delimited JSON 传输；旧客户端用 Content-Length framing。
        global _NEGOTIATED_VERSION
        params = msg.get("params", {}) if isinstance(msg.get("params"), dict) else {}
        req_ver = params.get("protocolVersion", "")
        # 服务器支持的最新版本（tools 协议自 2024-11-05 起稳定）
        _SUPPORTED = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")
        chosen = req_ver if req_ver in _SUPPORTED else "2024-11-05"
        _NEGOTIATED_VERSION = chosen
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": chosen,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "yolo-mcp", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = msg.get("params", {})
        result = call_tool(params.get("name", ""), params.get("arguments", {}))
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    log(f"未处理的方法: {method}")
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def send_message(msg: dict) -> None:
    """按协商的协议版本写出一条消息到 stdout。

    - 2025+ 协议（mcp SDK 1.28 默认）：newline-delimited JSON（单行 + \\n）
    - 2024-11-05 协议（旧客户端/Claude Desktop）：Content-Length framing
    """
    global _NEGOTIATED_VERSION
    data = json.dumps(msg, ensure_ascii=False)
    buf = sys.stdout.buffer
    if _NEGOTIATED_VERSION in ("2025-03-26", "2025-06-18", "2025-11-25"):
        # 新版格式：单行 JSON + 换行
        buf.write(data.encode("utf-8") + b"\n")
    else:
        # 旧版格式：Content-Length framing
        body = data.encode("utf-8")
        buf.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
        buf.write(body)
    buf.flush()


def read_message() -> dict | None:
    """从 stdin 读出一条消息；EOF 返回 None。

    同时支持两种 MCP stdio framing：
    1. newline-delimited JSON（mcp SDK 1.28+ 默认：一行一个 JSON + \\n）
    2. Content-Length framing（旧格式：header + 空行 + body）
    """
    stdin = sys.stdin.buffer
    # 先尝试按行读取（newline-delimited 格式）
    # 通过 peek 判断是否以 "Content-Length:" 开头
    import select

    def _read_line() -> bytes | None:
        line = stdin.readline()
        return line

    # 逐行扫描：首行若不是 header 而是 JSON，则按 newline-delimited 处理
    while True:
        line = _read_line()
        if not line:
            return None  # EOF
        stripped = line.strip()
        if not stripped:
            continue  # 跳过空行（可能是 framing 之间的空行）
        # 若首行就是 JSON（以 { 开头），按 newline-delimited 处理
        if stripped.startswith(b"{"):
            try:
                return json.loads(stripped.decode("utf-8"))
            except (ValueError, TypeError):
                continue  # 解析失败，继续读
        # 否则按 Content-Length header 解析
        if stripped.lower().startswith(b"content-length:"):
            try:
                content_length = int(stripped.split(b":", 1)[1].strip())
            except (ValueError, TypeError):
                content_length = 0
            # 读空行（header 结束）
            while True:
                blank = _read_line()
                if not blank:
                    return None
                if blank.strip() == b"":
                    break
            body = stdin.read(content_length)
            if not body or len(body) < content_length:
                return None
            try:
                return json.loads(body.decode("utf-8"))
            except (ValueError, TypeError):
                continue
        # 其他 header 行，跳过继续读
        continue


def main() -> None:
    log("yolo-mcp 启动，等待 MCP 客户端连接...")
    while True:
        try:
            msg = read_message()
        except (json.JSONDecodeError, ValueError) as e:
            log(f"消息解析失败: {e}")
            continue
        if msg is None:
            log("连接关闭，退出")
            return
        resp = handle(msg)
        if resp is not None:
            send_message(resp)


if __name__ == "__main__":
    main()

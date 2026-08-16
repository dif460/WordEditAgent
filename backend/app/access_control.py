"""设备访问控制：MAC 白名单 + 设备凭证 Cookie。

规则（严格白名单模式，ACCESS_CONTROL_MODE=mac 时生效）：
1. 本机请求（127.0.0.1 / ::1）始终放行。
2. 携带有效设备凭证 Cookie（wea_device_allow）且其 MAC 仍在该设备白名单中的请求放行。
3. 局域网请求通过 ARP 解析客户端 MAC；MAC 命中白名单 → 放行，并顺手发放设备凭证 Cookie。
4. 其余请求一律返回 403。

技术说明：MAC 地址只在局域网（二层）内可见。设备跨路由器（互联网）访问时服务器
无法解析其 MAC，只能依赖设备凭证 Cookie——该 Cookie 仅在设备从局域网访问且 MAC
命中白名单时签发，有效期长（默认 1 年），因此该设备之后无论是否在局域网、IP 如何
变化，都能凭 Cookie 访问；白名单中删除其 MAC 后，Cookie 同时失效。
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, Request, Response
from starlette.responses import JSONResponse

from app.config import settings

# 设备凭证 Cookie 名称
COOKIE_NAME = "wea_device_allow"
# ARP 缓存有效期（秒）
_ARP_TTL = 20.0
# 解析失败结果的缓存有效期（秒），避免对公网 IP 反复 ping
_ARP_MISS_TTL = 60.0

_arp_cache: dict[str, tuple[float, str | None]] = {}
_allowed_cache: dict[tuple[str, float], set[str]] = {}
_local_iface_cache: dict[str, tuple[float, dict[str, str]]] = {}

# Windows 下禁止弹出命令行窗口
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_MAC_RE = re.compile(r"^[0-9a-f]{12}$")
# ipconfig 中物理地址 / IPv4 地址行（兼容中英文系统）
_PHYS_RE = re.compile(r"(?:Physical Address|物理地址)[^:]*:\s*([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})")
_IPV4_RE = re.compile(r"(?:IPv4 Address|IPv4 地址)[^:]*:\s*([\d.]+)")


# ---------------------------------------------------------------- 工具函数

def normalize_mac(mac: str) -> str | None:
    """把任意格式的 MAC 归一化为 12 位小写十六进制；非法返回 None。"""
    if not mac:
        return None
    norm = re.sub(r"[^0-9a-fA-F]", "", mac).lower()
    return norm if _MAC_RE.match(norm) else None


def format_mac(mac_norm: str) -> str:
    """把归一化 MAC 格式化为 xx:xx:xx:xx:xx:xx 便于阅读。"""
    return ":".join(mac_norm[i : i + 2] for i in range(0, 12, 2))


def strip_ipv4_mapped(ip: str) -> str:
    if ip.startswith("::ffff:"):
        return ip[7:]
    return ip


def is_loopback(ip: str) -> bool:
    ip = strip_ipv4_mapped(ip)
    return ip == "::1" or ip.startswith("127.") or ip == "::ffff:127.0.0.1"


# ---------------------------------------------------------------- 白名单加载

def _allowed_macs_path() -> Path:
    return settings.allowed_macs_path


def load_allowed_macs() -> set[str]:
    """读取白名单文件（按文件 mtime 缓存，改文件无需重启即生效）。

    文件格式：{"allowed_macs": ["96-75-74-fd-e5-98", ...]}（也兼容直接写数组）。
    """
    path = _allowed_macs_path()
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return set()
    key = (str(path), mtime)
    if key in _allowed_cache:
        return _allowed_cache[key]
    macs: set[str] = set()
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("allowed_macs", [])
        if isinstance(data, list):
            for item in data:
                norm = normalize_mac(str(item))
                if norm:
                    macs.add(norm)
    except (OSError, json.JSONDecodeError):
        pass
    _allowed_cache[key] = macs
    return macs


# ---------------------------------------------------------------- 设备凭证

def get_device_secret() -> str:
    """返回 HMAC 签名密钥：优先用环境变量；为空则读取/生成 .device_cookie_secret。"""
    if settings.device_cookie_secret:
        return settings.device_cookie_secret
    path = Path(__file__).resolve().parent.parent / ".device_cookie_secret"
    try:
        secret = path.read_text(encoding="utf-8").strip()
        if secret:
            return secret
    except OSError:
        pass
    secret = os.urandom(32).hex()
    try:
        path.write_text(secret, encoding="utf-8")
    except OSError:
        pass  # 写不进去就退化为进程内临时密钥（重启后 Cookie 失效）
    return secret


def _sign(mac_norm: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), mac_norm.encode("ascii"), hashlib.sha256).hexdigest()


def make_cookie_value(mac_norm: str) -> str:
    return f"{mac_norm}:{_sign(mac_norm, get_device_secret())}"


def verify_cookie(value: str | None) -> str | None:
    """校验 Cookie，返回其中的归一化 MAC；无效返回 None。"""
    if not value:
        return None
    mac, sep, sig = value.partition(":")
    if not sep:
        return None
    mac_norm = normalize_mac(mac)
    if not mac_norm:
        return None
    expect = _sign(mac_norm, get_device_secret())
    if hmac.compare_digest(sig, expect):
        return mac_norm
    return None


# ---------------------------------------------------------------- ARP 解析

def _decode_best(raw: bytes) -> str:
    """兼容系统本地编码（中文 Windows 为 GBK）的宽容解码。IP/MAC 行是纯 ASCII。"""
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _run_arp(ip: str) -> str | None:
    """执行系统 arp 命令解析 IP 的 MAC；失败返回 None。"""
    if sys.platform == "win32":
        cmd = ["arp", "-a"]
    else:
        cmd = ["ip", "neigh"] if sys.platform.startswith("linux") else ["arp", "-an"]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=5,
            creationflags=_NO_WINDOW,
        )
        out = _decode_best(proc.stdout or b"")
    except Exception:
        return None
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == ip:
            for token in parts[1:4]:
                norm = normalize_mac(token)
                if norm:
                    return norm
        # Linux `ip neigh` 格式：192.168.1.7 dev eth0 lladdr 96:75:74:fd:e5:98 ...
        for i, token in enumerate(parts):
            if token == "lladdr" and i + 1 < len(parts):
                norm = normalize_mac(parts[i + 1])
                if norm and parts[0] == ip:
                    return norm
    return None


def _ping(ip: str) -> None:
    """短超时 ping，用于刷新 ARP 表。"""
    try:
        if sys.platform == "win32":
            cmd = ["ping", "-n", "1", "-w", "500", ip]
        else:
            cmd = ["ping", "-c", "1", "-W", "1", ip]
        subprocess.run(
            cmd,
            capture_output=True,
            timeout=5,
            creationflags=_NO_WINDOW,
        )
    except Exception:
        pass


def resolve_mac(ip: str) -> str | None:
    """解析客户端 IP 的 MAC，带缓存。命中失败会先 ping 一次再查。"""
    ip = strip_ipv4_mapped(ip)
    if is_loopback(ip):
        return None
    now = time.monotonic()
    if ip in _arp_cache:
        ts, mac = _arp_cache[ip]
        ttl = _ARP_MISS_TTL if mac is None else _ARP_TTL
        if now - ts < ttl:
            return mac
    mac = _run_arp(ip)
    if mac is None:
        _ping(ip)
        mac = _run_arp(ip)
    _arp_cache[ip] = (time.monotonic(), mac)
    return mac


# ---------------------------------------------------------------- 本机接口识别

def _local_interfaces() -> dict[str, str]:
    """本机接口 IP → MAC 映射（ipconfig /all 解析），带缓存。

    ARP 表不含本机自身 IP，而浏览器通过本机局域网 IP 访问时源地址正是本机 IP，
    因此需要单独识别：本机自身发起的请求一律视为可信（本机管理员）。
    """
    now = time.monotonic()
    if _local_iface_cache:
        ts, mapping = _local_iface_cache["_"]
        if now - ts < 600:
            return mapping
    mapping: dict[str, str] = {}
    try:
        proc = subprocess.run(
            ["ipconfig", "/all"],
            capture_output=True,
            timeout=10,
            creationflags=_NO_WINDOW,
        )
        text = _decode_best(proc.stdout or b"")
    except Exception:
        text = ""
    for block in re.split(r"(?m)^(?=\S)", text):
        m = _PHYS_RE.search(block)
        if not m:
            continue
        mac_norm = normalize_mac(m.group(1))
        if not mac_norm:
            continue
        for ip in _IPV4_RE.findall(block):
            mapping[ip.strip()] = mac_norm
    _local_iface_cache["_"] = (time.monotonic(), mapping)
    return mapping


def is_local_ip(ip: str) -> bool:
    """该 IP 是否为运行本程序的主机自身接口地址。"""
    ip = strip_ipv4_mapped(ip)
    return ip in _local_interfaces()


# ---------------------------------------------------------------- 请求判定

def evaluate_request(request: Request) -> tuple[str | None, str | None]:
    """返回 (拒绝原因, 需签发的 MAC)；放行时拒绝原因为 None。

    - 拒绝原因非 None：应返回 403。
    - 第二项非 None：该 MAC 命中白名单，放行且需给响应签发设备 Cookie。
    """
    client = request.client
    ip = client.host if client else ""
    ip = strip_ipv4_mapped(ip)

    if is_loopback(ip):
        return None, None

    # 本机自身接口 IP（浏览器经 192.168.x.x 访问本程序时源地址为本机 IP，ARP 无法解析自己）
    if is_local_ip(ip):
        return None, None

    # 1) 已有有效设备凭证
    raw = request.cookies.get(COOKIE_NAME)
    if raw:
        mac_norm = verify_cookie(raw)
        if mac_norm:
            if mac_norm in load_allowed_macs():
                return None, None
            return (
                f"设备凭证已失效：MAC {format_mac(mac_norm)} 已不在白名单中，访问被拒绝",
                None,
            )

    # 2) 局域网内按 ARP 解析 MAC
    mac = resolve_mac(ip)
    if mac is None:
        return (
            f"无法验证设备身份：请求来自 {ip}，该地址不在本局域网内（无法获取其 MAC 地址）。"
            f"如该设备曾在局域网内访问过并持有设备凭证，请重新从局域网登录一次，"
            f"或联系管理员把该设备加入白名单。",
            None,
        )
    if mac in load_allowed_macs():
        return None, mac
    return (
        f"设备访问被拒绝：来源 {ip} 的 MAC 地址 {format_mac(mac)} 不在白名单中。"
        f"如需放行，请把该 MAC 加入 backend/allowed_devices.json 后刷新页面重试。",
        None,
    )


def issue_device_cookie(response: Response, mac_norm: str) -> None:
    """给响应附加设备凭证 Cookie。"""
    response.set_cookie(
        key=COOKIE_NAME,
        value=make_cookie_value(mac_norm),
        max_age=settings.device_cookie_max_age,
        path="/",
        httponly=True,
        samesite="lax",
    )


class DeviceAccessControlMiddleware(BaseHTTPMiddleware):
    """严格白名单中间件（内层，CORS 在其外层负责预检与跨域头）。"""

    async def dispatch(self, request: Request, call_next):
        if settings.access_control_mode != "mac":
            return await call_next(request)
        reason, mac = evaluate_request(request)
        if reason is not None:
            return JSONResponse(status_code=403, content={"detail": reason})
        response = await call_next(request)
        if mac is not None:
            issue_device_cookie(response, mac)
        return response

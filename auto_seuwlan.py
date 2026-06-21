#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import re
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple
from urllib import error, parse, request


APP_NAME = "auto-seuwlan"
VERSION = "0.2.0"

URL_RE = re.compile(r"https?://[^\s<>()\"']+")
LOG_FILE: Optional[Path] = None

DEFAULT_CHECK_URLS = (
    "http://www.msftconnecttest.com/connecttest.txt",
    "http://1.1.1.1",
    "http://www.baidu.com/",
)

RET_CODE_MESSAGES = {
    "0": ("login accepted", True),
    "1": ("incorrect username or password", False),
    "2": ("this IP is already online", True),
    "3": ("portal system is busy", False),
    "4": ("unknown portal error", False),
    "5": ("challenge request failed", False),
    "6": ("challenge request timed out", False),
    "7": ("authentication failed", False),
    "8": ("authentication timed out", False),
    "9": ("logout failed", False),
    "10": ("logout timed out", False),
}

SENSITIVE_QUERY_KEYS = {
    "password",
    "passwd",
    "pass",
    "user_password",
    "user_account",
    "username",
    "account",
    "wlan_user_mac",
    "wlanusermac",
    "mac",
}


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


@dataclass(frozen=True)
class HttpResult:
    status: int
    body: str
    headers: Dict[str, str]
    url: str


@dataclass(frozen=True)
class ProbeResult:
    online: bool
    portal_url: Optional[str]
    status: Optional[int]
    message: str


def configure_logging(log_file: str) -> None:
    global LOG_FILE
    LOG_FILE = None
    if not log_file:
        return
    path = Path(log_file).expanduser()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE = path
    except OSError as exc:
        print(f"[{timestamp()}] WARN  cannot create log directory for {path}: {exc}", flush=True)


def timestamp() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def log(level: str, message: str) -> None:
    line = f"[{timestamp()}] {level.upper():5s} {message}"
    print(line, flush=True)
    if not LOG_FILE:
        return
    try:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def get_str(args: argparse.Namespace, attr: str, env_name: str, default: str = "") -> str:
    value = getattr(args, attr, None)
    if value is None:
        value = os.environ.get(env_name, default)
    return "" if value is None else str(value).strip()


def get_int(args: argparse.Namespace, attr: str, env_name: str, default: int) -> int:
    value = get_str(args, attr, env_name, str(default))
    try:
        return int(value)
    except ValueError:
        return default


def get_float(args: argparse.Namespace, attr: str, env_name: str, default: float) -> float:
    value = get_str(args, attr, env_name, str(default))
    try:
        return float(value)
    except ValueError:
        return default


def env_flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def split_urls(value: str) -> Tuple[str, ...]:
    urls = tuple(part.strip() for part in re.split(r"[,;]", value) if part.strip())
    return urls or DEFAULT_CHECK_URLS


def looks_like_placeholder_url(url: str) -> bool:
    lowered = url.lower()
    return any(token in lowered for token in ("...", "<", ">", "10.x", "your_", "your-"))


def extract_first_url_from_markdown(path: Path) -> Optional[str]:
    if not path.exists() or path.stat().st_size == 0:
        return None
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    match = URL_RE.search(text)
    if not match:
        return None
    url = match.group(0).rstrip(".,;]}>，。；")
    return None if looks_like_placeholder_url(url) else url


def configured_login_url(args: argparse.Namespace) -> Tuple[Optional[str], str]:
    direct = get_str(args, "login_url", "SEUWLAN_LOGIN_URL", "")
    if direct and not looks_like_placeholder_url(direct):
        return direct, "SEUWLAN_LOGIN_URL"

    md_path = Path(get_str(args, "md", "SEUWLAN_MARKDOWN", "seuwlan.md"))
    url = extract_first_url_from_markdown(md_path)
    if url:
        return url, str(md_path)
    return None, str(md_path)


def infer_portal_type(url: Optional[str]) -> str:
    if not url:
        return "unknown"
    parsed = parse.urlparse(url)
    path = parsed.path.lower()
    query = {key.lower() for key in parse.parse_qs(parsed.query)}
    host = (parsed.hostname or "").lower()

    if "srun" in host or "srun" in path or "ac_id" in query:
        return "srun"
    if "interface.do" in path or "querystring" in query:
        return "h3c_eportal"
    if "ddddd" in query or "upass" in query or "drcom" in path:
        return "drcom_legacy"
    if (
        "eportal" in path
        or {"userip", "wlanuserip", "wlanacname", "wlanacip"} & query
        or path.endswith(("/a79.htm", "/a40.htm", "/a41.htm", "/a42.htm"))
    ):
        return "seu_eportal"
    return "unknown"


def mask(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def mask_ip(value: str) -> str:
    parts = value.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        return f"{parts[0]}.{parts[1]}.*.*"
    return mask(value)


def redact_url(url: str) -> str:
    parsed = parse.urlparse(url)
    if not parsed.query:
        return url

    redacted_pairs = []
    for key, value in parse.parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in SENSITIVE_QUERY_KEYS:
            value = "***"
        elif lowered in {"userip", "wlan_user_ip", "wlanuserip"}:
            value = mask_ip(value)
        redacted_pairs.append((key, value))
    return parse.urlunparse(parsed._replace(query=parse.urlencode(redacted_pairs)))


def build_opener(allow_redirects: bool, use_proxy: bool) -> request.OpenerDirector:
    handlers = [request.HTTPSHandler(context=ssl._create_unverified_context())]
    if not use_proxy:
        handlers.insert(0, request.ProxyHandler({}))
    if not allow_redirects:
        handlers.append(NoRedirect())
    return request.build_opener(*handlers)


def http_get(
    url: str,
    params: Optional[Dict[str, str]] = None,
    timeout: float = 5.0,
    allow_redirects: bool = True,
    use_proxy: bool = False,
) -> HttpResult:
    if params:
        separator = "&" if parse.urlparse(url).query else "?"
        url = f"{url}{separator}{parse.urlencode(params)}"
    opener = build_opener(allow_redirects=allow_redirects, use_proxy=use_proxy)
    req = request.Request(
        url,
        headers={
            "User-Agent": f"Mozilla/5.0 ({APP_NAME}/{VERSION})",
            "Accept": "*/*",
            "Connection": "close",
        },
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            body = resp.read(1024 * 1024).decode("utf-8", errors="replace")
            return HttpResult(resp.status, body, dict(resp.headers.items()), resp.geturl())
    except error.HTTPError as exc:
        body = exc.read(1024 * 1024).decode("utf-8", errors="replace")
        return HttpResult(exc.code, body, dict(exc.headers.items()), exc.geturl())
    except (error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(str(exc)) from exc


def probe_connectivity(check_urls: Iterable[str], timeout: float, use_proxy: bool) -> ProbeResult:
    last_error = "all connectivity probes failed"
    for check_url in check_urls:
        try:
            result = http_get(check_url, timeout=timeout, allow_redirects=False, use_proxy=use_proxy)
        except RuntimeError as exc:
            last_error = f"{check_url}: {exc}"
            continue

        location = result.headers.get("Location") or result.headers.get("location")
        if 300 <= result.status < 400 and location:
            redirected = parse.urljoin(check_url, location)
            portal_type = infer_portal_type(redirected)
            if portal_type != "unknown":
                return ProbeResult(False, redirected, result.status, f"portal redirect: {portal_type}")
            return ProbeResult(True, None, result.status, f"{check_url} redirected normally")

        body_head = result.body[:2048].lower()
        if infer_portal_type(result.url) != "unknown" or "eportal" in body_head:
            return ProbeResult(False, result.url, result.status, "portal page returned")
        if result.status in (200, 204, 301, 302):
            return ProbeResult(True, None, result.status, f"{check_url} returned {result.status}")

        last_error = f"{check_url} returned {result.status}"

    return ProbeResult(False, None, None, last_error)


def connect_wifi(profile: str, wait_seconds: float) -> bool:
    if not profile:
        return True
    if platform.system().lower() != "windows":
        log("warn", "Wi-Fi reconnect is only implemented through Windows netsh; skipping")
        return True

    cmd = ["netsh", "wlan", "connect", f"name={profile}"]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log("warn", f"failed to invoke netsh: {exc}")
        return False

    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode == 0:
        log("info", f"requested Wi-Fi connection to profile '{profile}'")
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        return True
    log("warn", f"netsh could not connect '{profile}': {output}")
    return False


def first_query_value(parsed_url: parse.ParseResult, keys: Iterable[str]) -> str:
    values = parse.parse_qs(parsed_url.query, keep_blank_values=True)
    lowered = {key.lower(): value for key, value in values.items()}
    for key in keys:
        hit = lowered.get(key.lower())
        if hit:
            return hit[0]
    return ""


def portal_endpoint(login_url: str, scheme: str) -> str:
    parsed = parse.urlparse(login_url)
    host = parsed.hostname
    if not host:
        raise ValueError(f"cannot parse portal host from URL: {redact_url(login_url)}")
    port = parsed.port or 801
    return f"{scheme}://{host}:{port}/eportal/"


def apply_isp_suffix(username: str, isp: str) -> str:
    if "@" in username:
        return username
    value = isp.strip().lower()
    suffixes = {
        "c": "cmcc",
        "cmcc": "cmcc",
        "mobile": "cmcc",
        "t": "telecom",
        "telecom": "telecom",
        "u": "unicom",
        "unicom": "unicom",
    }
    suffix = suffixes.get(value)
    return f"{username}@{suffix}" if suffix else username


def parse_jsonp(body: str) -> Dict[str, object]:
    text = body.strip()
    if not text:
        return {}
    if text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    elif "(" in text and text.endswith(")"):
        text = text[text.find("(") + 1 : -1]
    if not text.startswith("{"):
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def summarize_portal_response(body: str) -> Tuple[bool, str]:
    data = parse_jsonp(body)
    if data:
        result = str(data.get("result", ""))
        ret_code = str(data.get("ret_code", ""))
        portal_msg = str(data.get("msg") or data.get("error") or "").strip()
        if result == "1":
            return True, portal_msg or "portal login succeeded"
        if ret_code in RET_CODE_MESSAGES:
            message, ok = RET_CODE_MESSAGES[ret_code]
            if portal_msg:
                message = f"{message}: {portal_msg}"
            return ok, message
        return False, f"portal rejected login: result={result or '-'} ret_code={ret_code or '-'} msg={portal_msg or '-'}"

    text = body.strip()
    lowered = text.lower()
    if '"result":"1"' in text or '"result":1' in text or "success" in lowered or "成功" in text:
        return True, "portal response looks successful"
    excerpt = " ".join(text.split())[:240]
    return False, excerpt or "empty portal response"


def login_seu_eportal(
    login_url: str,
    username: str,
    password: str,
    isp: str,
    mac: str,
    timeout: float,
    dry_run: bool,
    use_proxy: bool,
    callback: str,
    js_version: str,
) -> Tuple[bool, str]:
    parsed = parse.urlparse(login_url)
    login_user = apply_isp_suffix(username, isp)
    wlan_user_ip = first_query_value(parsed, ("UserIP", "wlanuserip", "wlan_user_ip"))
    wlan_ac_name = first_query_value(parsed, ("wlanacname", "wlan_ac_name"))
    wlan_ac_ip = first_query_value(parsed, ("wlanacip", "wlan_ac_ip"))

    params = {
        "c": "Portal",
        "a": "login",
        "callback": callback,
        "login_method": "1",
        "user_account": f",0,{login_user}",
        "user_password": password,
        "wlan_user_ip": wlan_user_ip,
        "wlan_user_ipv6": "",
        "wlan_user_mac": mac or "000000000000",
        "wlan_ac_ip": wlan_ac_ip,
        "wlan_ac_name": wlan_ac_name,
        "jsVersion": js_version,
        "v": str(random.randint(1000, 9999)),
    }

    if dry_run:
        endpoint = portal_endpoint(login_url, "http")
        return True, f"dry run: would login through {endpoint} as {mask(login_user)}"

    last_message = ""
    for scheme in ("http", "https"):
        try:
            endpoint = portal_endpoint(login_url, scheme)
            result = http_get(endpoint, params=params, timeout=timeout, allow_redirects=True, use_proxy=use_proxy)
        except (RuntimeError, ValueError) as exc:
            last_message = str(exc)
            continue

        ok, message = summarize_portal_response(result.body)
        if result.status == 200:
            return ok, message
        last_message = f"{endpoint} returned HTTP {result.status}: {message}"
        if result.status != 400:
            break

    return False, last_message or "no portal endpoint responded"


def run_once(args: argparse.Namespace) -> bool:
    timeout = get_float(args, "timeout", "SEUWLAN_TIMEOUT", 5.0)
    check_urls = split_urls(get_str(args, "check_urls", "SEUWLAN_CHECK_URLS", ",".join(DEFAULT_CHECK_URLS)))
    use_proxy = args.use_system_proxy or env_flag("SEUWLAN_USE_SYSTEM_PROXY", False)
    configured_url, configured_source = configured_login_url(args)
    login_url = configured_url

    if not args.force:
        probe = probe_connectivity(check_urls, timeout, use_proxy)
        if probe.online:
            log("info", f"already online ({probe.message})")
            return True
        if probe.portal_url:
            login_url = probe.portal_url
            log("info", f"network needs authentication ({probe.message}); using live portal URL")
        else:
            log("info", f"network needs authentication ({probe.message})")

    profile = get_str(args, "wifi_profile", "SEUWLAN_WIFI_PROFILE", "SEU-WLAN")
    wait_seconds = get_float(args, "wifi_wait", "SEUWLAN_WIFI_WAIT", 5.0)
    skip_wifi = args.skip_wifi or env_flag("SEUWLAN_SKIP_WIFI", False)
    if skip_wifi:
        log("info", "Wi-Fi reconnect skipped by configuration")
    elif args.dry_run:
        log("info", f"dry run: would request Wi-Fi connection to profile '{profile}'")
    else:
        connect_wifi(profile, wait_seconds)

    if not login_url:
        probe = probe_connectivity(check_urls, timeout, use_proxy)
        if probe.portal_url:
            login_url = probe.portal_url

    if not login_url:
        log("error", f"no portal URL found; set SEUWLAN_LOGIN_URL or put the redirected URL in {configured_source}")
        return False

    portal_type = infer_portal_type(login_url)
    log("info", f"detected portal type: {portal_type}")
    if portal_type != "seu_eportal":
        log("error", f"unsupported portal type for auto-login: {portal_type}; URL={redact_url(login_url)}")
        return False

    username = get_str(args, "username", "SEUWLAN_USERNAME", "")
    password = get_str(args, "password", "SEUWLAN_PASSWORD", "")
    if not username or not password:
        log("error", "missing SEUWLAN_USERNAME or SEUWLAN_PASSWORD")
        return False

    isp = get_str(args, "isp", "SEUWLAN_ISP", "")
    mac = get_str(args, "mac", "SEUWLAN_MAC", "000000000000")
    callback = get_str(args, "callback", "SEUWLAN_CALLBACK", "dr1003")
    js_version = get_str(args, "js_version", "SEUWLAN_JS_VERSION", "3.3.3")
    ok, message = login_seu_eportal(
        login_url,
        username,
        password,
        isp,
        mac,
        timeout,
        args.dry_run,
        use_proxy,
        callback,
        js_version,
    )
    log("info" if ok else "error", message)
    if not ok or args.dry_run:
        return ok

    time.sleep(2)
    verify = probe_connectivity(check_urls, timeout, use_proxy)
    if verify.online:
        log("info", "connectivity verified after login")
        return True
    log("warn", f"login request finished, but connectivity check still failed: {verify.message}")
    return False


def detect(args: argparse.Namespace) -> int:
    url, source = configured_login_url(args)
    if not url:
        print(f"source: {source}")
        print("login_url: <none>")
        print("portal_type: unknown")
        print("note: no URL was found; paste the redirected login URL into seuwlan.md or SEUWLAN_LOGIN_URL")
        return 1
    print(f"source: {source}")
    print(f"login_url: {redact_url(url)}")
    print(f"portal_type: {infer_portal_type(url)}")
    return 0


def command_exists(command: str) -> bool:
    try:
        subprocess.run([command, "/?" if command.lower() == "netsh" else "--version"], capture_output=True, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def scheduled_task_exists(task_name: str) -> Optional[bool]:
    if platform.system().lower() != "windows":
        return None
    try:
        result = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", task_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.returncode == 0


def yesno(value: bool) -> str:
    return "yes" if value else "no"


def doctor(args: argparse.Namespace) -> int:
    env_path = Path(args.env)
    url, source = configured_login_url(args)
    use_proxy = args.use_system_proxy or env_flag("SEUWLAN_USE_SYSTEM_PROXY", False)
    task_name = get_str(args, "task_name", "SEUWLAN_TASK_NAME", "Auto SEU-WLAN")
    task_exists = scheduled_task_exists(task_name)

    print(f"{APP_NAME} {VERSION}")
    print(f"python: {sys.version.split()[0]} ({sys.executable})")
    print(f"platform: {platform.platform()}")
    print(f"cwd: {Path.cwd()}")
    print(f"env_file: {env_path} ({'exists' if env_path.exists() else 'missing'})")
    print(f"username_configured: {yesno(bool(os.environ.get('SEUWLAN_USERNAME')))}")
    print(f"password_configured: {yesno(bool(os.environ.get('SEUWLAN_PASSWORD')))}")
    print(f"wifi_profile: {get_str(args, 'wifi_profile', 'SEUWLAN_WIFI_PROFILE', 'SEU-WLAN')}")
    print(f"use_system_proxy: {yesno(use_proxy)}")
    print(f"portal_url_source: {source}")
    print(f"portal_url: {redact_url(url) if url else '<none>'}")
    print(f"portal_type: {infer_portal_type(url)}")
    print(f"netsh_available: {yesno(command_exists('netsh')) if platform.system().lower() == 'windows' else 'n/a'}")
    if task_exists is None:
        print("scheduled_task: n/a")
    else:
        print(f"scheduled_task: {task_name} ({'exists' if task_exists else 'missing'})")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto reconnect and authenticate SEU-WLAN.")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {VERSION}")
    parser.add_argument("--env", default=".env", help="env file path, default: .env")
    parser.add_argument("--md", default=None, help="markdown file containing the portal redirect URL")
    parser.add_argument("--login-url", default=None, help="portal redirect URL; overrides markdown")
    parser.add_argument("--username", default=None, help="campus network username")
    parser.add_argument("--password", default=None, help="campus network password")
    parser.add_argument("--wifi-profile", default=None, help="Windows Wi-Fi profile name")
    parser.add_argument("--wifi-wait", default=None, help="seconds to wait after netsh connect")
    parser.add_argument("--skip-wifi", action="store_true", help="skip netsh Wi-Fi reconnect")
    parser.add_argument("--isp", default=None, help="empty for campus network; c/cmcc, t/telecom, u/unicom for ISP")
    parser.add_argument("--mac", default=None, help="MAC value sent to the portal, default: 000000000000")
    parser.add_argument("--callback", default=None, help="ePortal JSONP callback name")
    parser.add_argument("--js-version", default=None, help="ePortal jsVersion parameter")
    parser.add_argument("--check-urls", default=None, help="comma separated connectivity probe URLs")
    parser.add_argument("--interval", default=None, help="daemon check interval in seconds")
    parser.add_argument("--timeout", default=None, help="HTTP timeout in seconds")
    parser.add_argument("--log-file", default=None, help="append logs to this file")
    parser.add_argument("--task-name", default=None, help="scheduled task name used by --doctor")
    parser.add_argument("--daemon", action="store_true", help="keep checking and reconnecting")
    parser.add_argument("--force", action="store_true", help="try portal login even if probes say online")
    parser.add_argument("--detect", action="store_true", help="only detect portal type from configured URL")
    parser.add_argument("--doctor", action="store_true", help="print local configuration diagnostics without logging in")
    parser.add_argument("--dry-run", action="store_true", help="print what would be done without sending credentials")
    parser.add_argument(
        "--use-system-proxy",
        action="store_true",
        help="use system proxy for HTTP requests; default is direct/no proxy for captive portal login",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_env_file(Path(args.env))
    configure_logging(get_str(args, "log_file", "SEUWLAN_LOG_FILE", ""))

    if args.detect:
        return detect(args)
    if args.doctor:
        return doctor(args)

    if args.daemon:
        interval = max(10, get_int(args, "interval", "SEUWLAN_INTERVAL", 60))
        log("info", f"daemon started, interval={interval}s")
        while True:
            try:
                run_once(args)
            except KeyboardInterrupt:
                log("info", "daemon stopped")
                return 0
            except Exception as exc:  # noqa: BLE001 - daemon should keep running
                log("error", f"unexpected error: {exc}")
            time.sleep(interval)

    return 0 if run_once(args) else 1


if __name__ == "__main__":
    sys.exit(main())

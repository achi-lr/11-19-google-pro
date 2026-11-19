#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Google AI Ultra 0 元开通 —— 一键脚本

用法（三步）：
    python3 ultra0.py --check            # 1. 环境自检
    python3 ultra0.py accounts.txt       # 2. 批量跑号
    python3 ultra0.py --account a@b.com:密码:2FA密钥   # 单号

accounts.txt 每行一个号：
    email----password----recovery----totp

前置条件：
    - 一台已 root 的安卓手机，USB 连接，开了 USB 调试
    - 手机上已登录目标 Google 账号（脚本也能自动加）
    - 电脑装了 Python3 + frida（pip install frida）

脚本会自动：推 frida-server、推 BillingClient 模块、查 offer、用 eft-12month 拉起收银台，
只有在确认金额为 0 时才点「订阅」。
"""
import argparse, base64, hashlib, hmac, json, os, re, select, struct, subprocess, sys, threading, time
from pathlib import Path
import tempfile

# 人工确认闸门：网页版点「我已完成，继续」，命令行按回车
HUMAN_EVENT = threading.Event()
WAITING = {"on": False, "msg": ""}


def wait_human(msg: str, timeout: int = 600) -> bool:
    """遇到人机验证时暂停，等人处理完再继续。"""
    WAITING["on"] = True
    WAITING["msg"] = msg
    print(f"\n⏸  需要你操作：{msg}")
    print("   完成后按【回车】继续（网页版点「我已完成，继续」）", flush=True)
    HUMAN_EVENT.clear()
    end = time.time() + timeout
    while time.time() < end:
        if HUMAN_EVENT.is_set():
            break
        try:
            r, _, _ = select.select([sys.stdin], [], [], 0.5)
            if r:
                sys.stdin.readline()
                break
        except Exception:
            time.sleep(0.5)
    WAITING["on"] = False
    print("▶  继续执行", flush=True)
    return True

# ---------- 常量 ----------
PKG = "com.google.android.apps.subscriptions.red"   # Google One
VENDING = "com.android.vending"                     # Play 商店
GMS = "com.google.android.gms"
PRODUCT = "g1.play.20tb"                            # Ultra 5x / 20TB
OFFER = "eft-12month"                               # 首年免费
MODULE_REMOTE = "/data/local/tmp/module_521.apk"
FRIDA_REMOTE = "/data/local/tmp/frida-server"
REPORT_DIR = Path("ultra0-report")

ADB_CANDIDATES = [
    str(Path(__file__).resolve().parent / 'platform-tools' / 'adb.exe'),
    os.environ.get("ADB_PATH", ""),
    # Windows / MuMu
    r"C:\Program Files\Netease\MuMuPlayer-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMuPlayerGlobal-12.0\shell\adb.exe",
    r"C:\Program Files\Netease\MuMu\emulator\nemu\vmonitor\bin\adb_server.exe",
    r"C:\Program Files\Netease\MuMu\nx_main\adb.exe",
    r"C:\Program Files (x86)\Netease\MuMuPlayer-12.0\shell\adb.exe",
    "adb.exe", "adb",
    # macOS / Linux
    os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
    "/opt/homebrew/bin/adb", "/usr/local/bin/adb", "/usr/bin/adb",
]


# ---------- 基础工具 ----------
def find_adb() -> str:
    for c in ADB_CANDIDATES:
        if not c:
            continue
        if c in ("adb", "adb.exe") or Path(c).exists():
            try:
                subprocess.run([c, "version"], capture_output=True, timeout=5)
                return c
            except Exception:
                continue
    sys.exit("❌ 找不到 adb，请安装 Android platform-tools 并加入 PATH")


ADB = None
SERIAL = None


def sh(*args, timeout=60, check=False, binary=False):
    cmd = [ADB] + (["-s", SERIAL] if SERIAL else []) + list(args)
    p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    if check and p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore")[:300])
    return p.stdout if binary else p.stdout.decode("utf-8", "ignore").strip()


def note(msg):
    print(f"   {msg}", flush=True)


def step(msg):
    print(f"\n▶ {msg}", flush=True)


def ok(msg):
    print(f"   ✅ {msg}", flush=True)


def warn(msg):
    print(f"   ⚠️  {msg}", flush=True)


# ---------- 设备 ----------
def pick_device():
    global SERIAL
    out = sh("devices")
    lines = [l for l in out.splitlines()[1:] if "\tdevice" in l]
    if not lines:
        # 模拟器：自动尝试常见端口
        for port in ("16384", "7555", "16416", "62001", "21503"):
            try:
                sh("connect", f"127.0.0.1:{port}", timeout=10)
            except Exception:
                pass
            out = sh("devices")
            lines = [l for l in out.splitlines()[1:] if "\tdevice" in l]
            if lines:
                note(f"已连接模拟器 127.0.0.1:{port}")
                break
    if not lines:
        sys.exit("❌ 没有检测到设备。MuMu 请确认已启动、开了 ADB 调试（设置里），或用 ADB_PATH 指定 adb。")
    SERIAL = lines[0].split("\t")[0]
    ok(f"设备已连接：{SERIAL}")


def ensure_root():
    def _id():
        try:
            return sh("shell", "id", timeout=15)
        except Exception:
            return ""

    uid = _id()
    if "uid=0" not in uid:
        # 模拟器常见：adb root 把 adbd 提权，无需 su
        try:
            sh("root", timeout=20)
            time.sleep(2)
            uid = _id()
            if "uid=0" in uid:
                note("已通过 adb root 提权")
        except Exception:
            pass
    if "uid=0" not in uid:
        try:
            uid = sh("shell", "su -c id", timeout=15)
        except Exception:
            uid = ""
    if "uid=0" not in uid:
        sys.exit("❌ 设备没有 root 权限。MuMu：设置里打开「ROOT 权限」并重启；或先手动执行 adb root。")


def ensure_frida_server():
    running = "frida-server" in sh("shell", "ps -A | grep frida-server || true")
    if running:
        ok("frida-server 已在运行")
        return
    if not sh("shell", f"ls {FRIDA_REMOTE} 2>/dev/null"):
        warn("设备上没有 frida-server，尝试用本地 frida 版本自动下载…")
        try:
            import frida
            ver = frida.__version__
        except Exception:
            sys.exit("❌ 电脑没装 frida。请先执行：pip3 install frida")
        abi = sh("shell", "getprop ro.product.cpu.abi").strip() or "arm64-v8a"
        arch = {"arm64-v8a": "arm64", "armeabi-v7a": "arm", "armeabi": "arm",
                "x86_64": "x86_64", "x86": "x86"}.get(abi, "arm64")
        note(f"设备 ABI={abi} → frida-server-{ver}-android-{arch}")
        url = (f"https://github.com/frida/frida/releases/download/{ver}/"
               f"frida-server-{ver}-android-{arch}.xz")
        import urllib.request, lzma
        tmp = Path(tempfile.gettempdir()) / "frida-server.xz"
        note(f"下载 {url}")
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            f.write(r.read())
        raw = Path(tempfile.gettempdir()) / "frida-server"
        with lzma.open(tmp, "rb") as fi, open(raw, "wb") as fo:
            fo.write(fi.read())
        sh("push", str(raw), FRIDA_REMOTE, timeout=180)
        sh("shell", f"chmod 755 {FRIDA_REMOTE}")
    is_root = "uid=0" in sh("shell", "id")
    if is_root:
        sh("shell", f"nohup {FRIDA_REMOTE} -D >/dev/null 2>&1 &", timeout=15)
    else:
        sh("shell", f"su -c 'nohup {FRIDA_REMOTE} -D >/dev/null 2>&1 &'", timeout=15)
    for _ in range(20):
        time.sleep(0.5)
        if "frida-server" in sh("shell", "ps -A | grep frida-server || true"):
            ok("frida-server 已启动")
            return
    sys.exit("❌ frida-server 启动失败")


def read_purchase_token(sku_short: str) -> str:
    """从 Play 商店的 library.db 里读出该 SKU 当前的 purchaseToken（叠加必需）。"""
    import tempfile, sqlite3, json as _json
    remote = "/data/local/tmp/lib_read.db"
    try:
        sh("shell", f"cp /data/data/{VENDING}/databases/library.db {remote} 2>/dev/null; chmod 666 {remote}", timeout=30)
    except Exception:
        pass
    tmp = Path(tempfile.gettempdir()) / "lib_read.db"
    try:
        if tmp.exists():
            tmp.unlink()
        sh("pull", remote, str(tmp), timeout=60)
    except Exception as e:
        warn(f"拉取 library.db 失败：{e}")
        return ""
    if not tmp.exists():
        return ""
    tok = ""
    try:
        con = sqlite3.connect(str(tmp))
        cur = con.cursor()
        rows = cur.execute(
            "select account, subs_valid_until_time, inapp_purchase_data "
            "from ownership where doc_id like ?",
            (f"%{sku_short}%",),
        ).fetchall()
        now_ms = int(time.time() * 1000)
        picked = None
        for account, valid, data in rows:
            if not data:
                continue
            try:
                j = _json.loads(data)
            except Exception:
                continue
            tk = j.get("purchaseToken")
            if not tk:
                continue
            try:
                alive = int(valid) > now_ms
            except Exception:
                alive = False
            # 优先取「未过期」的；多个账号都活跃时取到期时间最晚的
            if picked is None or (alive and not picked[2]) or (alive == picked[2] and int(valid or 0) > picked[3]):
                picked = (tk, account, alive, int(valid or 0))
        if picked:
            tok = picked[0]
            note(f"purchaseToken 来源账号：{picked[1]}（{'有效' if picked[2] else '已过期'}）")
        con.close()
    except Exception as e:
        warn(f"读取 library.db 失败：{e}")
    finally:
        try:
            tmp.unlink()
        except Exception:
            pass
    return tok


def ensure_vending():
    """BillingClient 需要 Play 商店进程在场，否则 queryProductDetails 永远不回调。"""
    if sh("shell", f"pidof {VENDING}"):
        ok("Play 商店进程在跑")
        return
    warn("Play 商店没在跑，正在拉起…")
    sh("shell", f"monkey -p {VENDING} -c android.intent.category.LAUNCHER 1", timeout=30)
    for _ in range(20):
        time.sleep(1)
        if sh("shell", f"pidof {VENDING}"):
            ok("Play 商店已拉起")
            time.sleep(2)
            return
    warn("Play 商店没起来，计费查询可能卡住（试试手动打开 Play 商店或重启模拟器）")


def ensure_module_apk():
    if sh("shell", f"ls {MODULE_REMOTE} 2>/dev/null"):
        ok("计费模块已就位")
        return
    note("正在推送计费模块（一次性）…")
    tmp = Path(tempfile.gettempdir()) / "module_521.apk"
    tmp.write_bytes(base64.b64decode(MODULE_B64))
    sh("push", str(tmp), MODULE_REMOTE, timeout=120)
    ok("计费模块已推送")


def ensure_network():
    proxy = sh("shell", "settings get global http_proxy")
    if proxy and proxy != "null" and proxy != ":0":
        sh("shell", "settings put global http_proxy :0")
        warn(f"已清除设备代理（原为 {proxy}），避免网络不通")
    # 关掉常见的 VPN 类应用，避免 fake-IP 导致 Play 连不上
    for p in ("com.github.metacubex.clash.meta", "com.github.kr328.clash"):
        if sh("shell", f"pm list packages | grep -q {p} && echo yes"):
            sh("shell", f"am force-stop {p}")
            warn(f"已临时关闭 {p}（它会拦截 Play 的网络）")


# ---------- UI ----------
def ui_xml() -> str:
    sh("shell", "uiautomator dump /sdcard/ui.xml")
    return sh("shell", "cat /sdcard/ui.xml")


def nodes(xml: str):
    for m in re.finditer(r"<node[^>]*>", xml):
        s = m.group(0)
        t = re.search(r'text="([^"]*)"', s)
        d = re.search(r'content-desc="([^"]*)"', s)
        b = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', s)
        c = re.search(r'class="([^"]*)"', s)
        if not b:
            continue
        yield {
            "text": (t.group(1) if t else "") or "",
            "desc": (d.group(1) if d else "") or "",
            "cls": (c.group(1) if c else "") or "",
            "x": (int(b.group(1)) + int(b.group(3))) // 2,
            "y": (int(b.group(2)) + int(b.group(4))) // 2,
        }


def tap(x, y):
    sh("shell", f"input tap {x} {y}")


def tap_text(*needles, exact=False) -> bool:
    for n in nodes(ui_xml()):
        label = n["text"] or n["desc"]
        if not label:
            continue
        hit = (label == needles[0]) if exact and needles else any(k in label for k in needles)
        if hit and (n["x"] or n["y"]):
            tap(n["x"], n["y"])
            return True
    return False


def type_text(s: str):
    sh("shell", f"input text '{s.replace(' ', '%s')}'")


def find_edit():
    for n in nodes(ui_xml()):
        if "EditText" in n["cls"]:
            return n["x"], n["y"]
    return None


# ---------- TOTP ----------
def totp(secret: str, digits=6, period=30) -> str:
    if not secret:
        return ""
    s = re.sub(r"[^A-Za-z2-7]", "", secret).upper()
    s += "=" * ((8 - len(s) % 8) % 8)
    key = base64.b32decode(s)
    ctr = int(time.time()) // period
    mac = hmac.new(key, struct.pack(">Q", ctr), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


# ---------- 账号 ----------
def accounts_on_device() -> list:
    out = sh("shell", "dumpsys account | grep 'type=com.google'")
    return out.splitlines()


def add_account(email, password, totp_secret="") -> bool:
    """把账号加到手机。没有 2FA 也能走；卡住时交给人处理。"""
    step(f"把账号加到手机：{email}")
    before = len(accounts_on_device())
    sh("shell", "am start -a android.settings.ADD_ACCOUNT_SETTINGS")
    time.sleep(3)
    tap_text("Google", exact=True) or tap_text("Google")
    time.sleep(5)

    pos = find_edit()
    if pos:
        for _ in range(3):                      # 输入后回读校验，防吞字
            tap(*pos); time.sleep(0.8)
            sh("shell", "input keyevent 123")   # 光标到行尾
            for _ in range(60):
                sh("shell", "input keyevent 67")  # 退格清空
            type_text(email); time.sleep(1)
            cur = " ".join(n["text"] for n in nodes(ui_xml()) if "@" in n["text"])
            if email.lower() in cur.lower():
                break
            warn(f"输入被吞，重试（当前：{cur[:40]}）")
        else:
            warn("邮箱多次输入不完整")
        tap_text("下一步", "Next"); time.sleep(6)

    if find_edit():
        tap(*find_edit()); time.sleep(1)
        type_text(password); time.sleep(1)
        tap_text("下一步", "Next"); time.sleep(7)

    # 逐步推进：已知界面自动点，未知/验证界面交给人
    unknown_rounds = 0
    for _ in range(90):
        if len(accounts_on_device()) > before:
            ok("账号已加入设备")
            return True
        xml = ui_xml()
        text = " ".join(n["text"] for n in nodes(xml) if n["text"])

        if "此账号已在您的设备上" in text or "already on your device" in text.lower():
            ok("账号已在设备上")
            return True
        if "找不到此账号" in text or "Couldn't find your Google Account" in text:
            warn("Google 说找不到这个账号（检查邮箱拼写）")
            return False
        if "密码不正确" in text or "Wrong password" in text:
            warn("密码不正确")
            return False

        if ("两步验证" in text or "2-Step" in text or "输入验证码" in text):
            if totp_secret and find_edit():
                code = totp(totp_secret)
                note(f"2FA 验证码：{code}")
                tap(*find_edit()); type_text(code); time.sleep(1)
                tap_text("下一步", "Next"); time.sleep(8)
                continue
            wait_human("手机上出现两步验证，请在手机上输入验证码完成", 300)
            continue

        if tap_text("以后再说", "Not now"):
            time.sleep(3); continue
        if tap_text("我同意", "I agree"):
            time.sleep(5); continue
        if tap_text("取消", "Skip", "跳过"):
            time.sleep(2); continue

        if any(k in text for k in ("证明您不是自动程序", "验证身份", "请输入电话号码", "无法验证", "确认是您本人")):
            wait_human("手机上出现人机/身份验证，请在手机上手动完成", 300)
            continue

        unknown_rounds += 1
        if unknown_rounds >= 8:
            wait_human("当前界面脚本不认识，请手动完成加号，完成后继续", 300)
            unknown_rounds = 0
        time.sleep(2)

    if len(accounts_on_device()) > before:
        ok("账号已加入设备")
        return True
    warn("加号超时")
    return False


def add_card(card: dict) -> bool:
    """在 Google Pay 里添加一张卡（卡号/有效期/CVC/持卡人/邮编）。"""
    if not card:
        return True
    step(f"添加付款方式：{card['number'][-4:].rjust(len(card['number']), '*')}")
    sh("shell", "am start -a android.intent.action.VIEW "
                "-d 'https://pay.google.com/gp/w/u/0/home/paymentmethods'")
    time.sleep(10)
    if not tap_text("Add a payment method", "添加付款方式", "添加信用卡", "Add card"):
        warn("没找到添加入口，跳过绑卡（可手动添加）")
        return False
    time.sleep(9)
    # 依次填：卡号 → 月 → 年 → CVC → 姓名 → 地址 → 城市
    edits = [n for n in nodes(ui_xml()) if "EditText" in n["cls"]]
    mm = re.sub(r"\D", "", card["exp"])[:2] or "01"
    yy = re.sub(r"\D", "", card["exp"])[2:][-2:] or "30"
    seq = [card["number"], mm, yy, card["cvc"], card["holder"] or "CARD HOLDER",
           "123 Main St", "Portland"]
    for i, val in enumerate(seq):
        edits = [n for n in nodes(ui_xml()) if "EditText" in n["cls"]]
        if i >= len(edits):
            break
        tap(edits[i]["x"], edits[i]["y"]); time.sleep(0.6)
        type_text(val); time.sleep(0.5)
    if not tap_text("Save", "保存"):
        wait_human("请手动点「保存」完成绑卡，然后继续", 240)
    else:
        time.sleep(8)
    ok("绑卡流程已提交")
    return True


def current_play_account() -> str:
    """读 Play 当前账号；读不到返回空串。"""
    for n in nodes(ui_xml()):
        if "账号和设置" in n["desc"] or "Account and settings" in n["desc"]:
            tap(n["x"], n["y"]); time.sleep(3); break
    best = ""
    for n in nodes(ui_xml()):
        m = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)", n["desc"] + " " + n["text"])
        if m:
            best = m.group(1).lower(); break
    sh("shell", "input keyevent 4")
    return best


def switch_play(email) -> bool:
    """切 Play 账号，UI 上确认不了就返回 False（绝不猜）。"""
    step(f"切换到 Play 账号：{email}")
    want = email.lower()
    sh("shell", f"am force-stop {VENDING}")
    sh("shell", f"am force-stop {PKG}")
    sh("shell", f"am start -n {VENDING}/com.google.android.finsky.activities.MainActivity "
                f"--es authAccount {email}")
    time.sleep(9)
    if current_play_account() == want:
        ok("Play 账号已确认"); return True
    for n in nodes(ui_xml()):
        if "账号和设置" in n["desc"] or "Account and settings" in n["desc"]:
            tap(n["x"], n["y"]); time.sleep(3); break
    for n in nodes(ui_xml()):
        if "展开账号列表" in n["desc"]:
            tap(n["x"], n["y"]); time.sleep(3); break
    for n in nodes(ui_xml()):
        if want in (n["text"] + " " + n["desc"]).lower():
            tap(n["x"], n["y"]); time.sleep(6); break
    sh("shell", "input keyevent 4")
    got = current_play_account()
    if got == want:
        ok("Play 账号已确认"); return True
    warn(f"Play 账号没切过来（当前：{got or '未知'}）——中止，避免跑错号")
    return False


# ---------- Frida ----------
def launch_app() -> int:
    sh("shell", f"am force-stop {PKG}")
    sh("shell", f"monkey -p {PKG} -c android.intent.category.LAUNCHER 1")
    time.sleep(7)
    pid = sh("shell", f"pidof {PKG}")
    return int(pid) if pid.strip().isdigit() else 0


def build_js(plan: str = "auto", list_only: bool = False, stack: bool = False, old_token: str = "", stack_mode=None) -> str:
    """按 plan 选择要查询的商品：5x=20TB，20x=30TB（隐藏带试用 ID）。"""
    js = FRIDA_JS
    if list_only:
        js = js.replace('var PREFER="";', 'var PREFER=""; var LIST_ONLY=true;', 1)
    if stack:
        js = js.replace('var PREFER="";', 'var PREFER=""; var STACK=true;', 1)
    if old_token:
        js = js.replace('var PREFER="";', 'var PREFER=""; var OLD_TOKEN="%s";' % old_token, 1)
    if stack_mode is not None:
        js = js.replace('var PREFER="";', 'var PREFER=""; var STACK_MODE=%d;' % stack_mode, 1)
    if plan == "20x":
        js = js.replace('var PRODUCTS=["g1.play.20tb","g1.play.ai.pro","g1.30tb"];',
                        'var PRODUCTS=["g1.play.ai.pro","g1.ai.pro","g1.30tb"];')
    elif plan == "5x":
        js = js.replace('var PRODUCTS=["g1.play.20tb","g1.play.ai.pro","g1.30tb"];',
                        'var PRODUCTS=["g1.play.20tb"];')
    elif plan.startswith("pro"):
        # Google AI Pro 5TB（g1.2tb.ai.subs_variant）：12months-eft / 6months-eft / 6months-eft-2 / 6months-eft-ss-2026
        prefer = {"pro12": "12months-eft", "pro6": "6months-eft",
                  "pro6b": "6months-eft-2", "pro6c": "6months-eft-ss-2026"}.get(plan, "12months-eft")
        js = js.replace('var PRODUCTS=["g1.play.20tb","g1.play.ai.pro","g1.30tb"];',
                        'var PRODUCTS=["g1.2tb.ai.subs_variant"];')
        js = js.replace('var PREFER="";', 'var PREFER="%s";' % prefer, 1)
    return js


def run_trial(pid: int, wait=90, plan="auto", list_only=False, stack=False, old_token="", stack_mode=None) -> dict:
    import frida
    step("注入计费模块，查询免费试用")
    dev = frida.get_usb_device(timeout=10)
    sess = dev.attach(pid)
    res = {"offers": [], "launched": None, "purchase": None, "errors": []}

    done = threading.Event()

    def on_msg(m, _):
        if m.get('type') == 'error':
            res['errors'].append(m)
            warn(str(m.get('stack') or m.get('description')))
            done.set()
            return
        p = m.get("payload") or {}
        ev = p.get("ev")
        if ev == "offer":
            res["offers"].append(p)
            note(f"offer {p.get('id')} → {p.get('micros')} ({p.get('period','')})")
            note(f"    token={p.get('token','')}")
        elif ev == "launched":
            res["launched"] = p
            done.set()
            ok(f"已拉起收银台：{p}")
        elif ev == 'list_only':
            done.set()
        elif ev == "purchase_cb":
            res["purchase"] = p
        elif ev and ("err" in ev or ev.startswith("no_")):
            res["errors"].append(p)
            warn(str(p))
            done.set()

    sc = sess.create_script(build_js(plan, list_only, stack, old_token, stack_mode))
    sc.on("message", on_msg)
    sc.load()
    if not done.wait(wait):
        warn('Timed out waiting for billing response')
    return res


def handle_verify(password="") -> bool:
    """买完可能要求重新输密码；顺手关掉 Play 积分提示。"""
    changed = False
    for _ in range(12):
        blob = " ".join(n["text"] for n in nodes(ui_xml()) if n["text"])
        if "以后再说" in blob or "Play 积分" in blob:
            tap_text("以后再说", "Not now"); time.sleep(2); changed = True; continue
        if ("验证" in blob or "Verify" in blob) and password:
            es = [n for n in nodes(ui_xml()) if "EditText" in n["cls"]]
            if es:
                tap(es[0]["x"], es[0]["y"]); time.sleep(0.8)
                slow_type(password, 0.1); time.sleep(0.8)
                tap_text("验证", "Verify"); time.sleep(6); changed = True; continue
        break
    return changed


def confirm_zero(wait=40, password="") -> dict:
    step("检查收银台金额（只在 0 元时确认）")
    out = {"price": None, "confirmed": False, "ineligible": False, "text": ""}
    for _ in range(wait // 2):
        xml = ui_xml()
        text = " ".join(n["text"] for n in nodes(xml) if n["text"])
        if "不符合免费试用条件" in text or "not eligible" in text.lower():
            warn("Play 提示：该账号不符合免费试用条件")
            if tap_text("知道了", "OK", "Got it"):
                time.sleep(2)
            out["ineligible"] = True
            return out
        if ("订阅" in text or "Subscribe" in text) and ("Ultra" in text or "AI" in text):
            out["text"] = text[:300]
            m = re.search(r"(US\$|HK\$|NT\$|\$|€|£)\s?([\d.,]+)", text)
            if m:
                out["price"] = m.group(0)
                try:
                    if float(m.group(2).replace(",", "")) == 0:
                        tap_text("订阅", "Subscribe")
                        out["confirmed"] = True
                        ok("已确认 0 元订阅")
                        return out
                except Exception:
                    pass
                warn(f"当前金额 {m.group(0)}，不是 0 元，不点确认")
                return out
            if ("不符合免费试用条件" in text) or ("not eligible" in text.lower()):
                out["ineligible"] = True
                warn("Play：该账号不符合免费试用条件，不点确认")
                tap_text("关闭", "取消", "Close"); return out
            if (re.search(r"(US\$|HK\$|NT\$|\$)\s?0(\.00)?\b", text)
                    or "US$0/月" in text or "US$0.00" in text
                    or re.search(r"免费试用\s*\d+\s*(个月|年|mo|month)", text)):
                tap_text("订阅", "Subscribe")
                out["confirmed"] = True
                ok("已确认免费试用")
                return out
        time.sleep(2)
    warn("没有检测到收银台（可能这个号已经订阅过）")
    return out


def verify() -> str:
    step("核对订阅状态")
    sh("shell", f"am start -a android.intent.action.VIEW "
                f"-d 'https://play.google.com/store/account/subscriptions'")
    time.sleep(9)
    text = " | ".join(n["text"] for n in nodes(ui_xml()) if n["text"])
    if "Ultra" in text:
        ok("订阅页已显示 Ultra")
    return text[:500]


# ---------- 单号流程 ----------
def process(email, password="", totp_secret="", add=True, card=None, plan="auto", no_switch=False, list_only=False, stack=False, old_token="", stack_mode=None) -> dict:
    print("\n" + "=" * 56)
    print(f"  处理账号：{email}")
    print("=" * 56)
    rec = {"email": email, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "status": "unknown"}
    if add:
        try:
            if not add_account(email, password, totp_secret):
                rec["status"] = "add_account_failed"
                return rec
        except Exception as e:
            warn(f"加号失败：{e}")
            rec["status"] = "add_account_error"
            return rec
    if card:
        try:
            add_card(card)
        except Exception as e:
            warn(f"绑卡失败：{e}")
    if globals().get("SKIP_ACCOUNT_CHECK"):
        ok("已跳过 Play 账号校验（--force）")
    elif list_only:
        cur = current_play_account()
        ok(f"列表模式：使用设备当前账号 {cur or '未知'}（不校验、不下单）")
    elif no_switch:
        cur = current_play_account()
        if cur != email.lower():
            warn(f"当前 Play 账号是 {cur or '未知'}，不是 {email}，中止")
            rec["status"] = "wrong_account"
            return rec
        ok("Play 账号已确认（手动切换模式）")
    elif not switch_play(email):
        rec["status"] = "play_account_switch_failed"
        return rec
    if stack and not old_token:
        note("正在读取当前订阅的 purchaseToken…")
        old_token = read_purchase_token("subs_variant")
        if old_token:
            ok(f"已读到 purchaseToken（{old_token[:16]}…），将用订阅升级模式叠加")
        else:
            warn("没读到 purchaseToken，将退回 queryPurchases 方式（可能拿不到）")

    pid = launch_app()
    if not pid:
        rec["status"] = "app_not_started"
        return rec
    fr = run_trial(pid, plan=plan, list_only=list_only, stack=stack, old_token=old_token, stack_mode=stack_mode)
    rec.update(fr)
    if list_only:
        rec["status"] = "listed"
        return rec
    if fr["launched"] and fr["launched"].get("code") == 0:
        rec["sheet"] = confirm_zero(password=password)
        rec["subscription_page"] = verify()
        rec["status"] = "subscribed" if "Ultra" in rec["subscription_page"] else "launched"
    else:
        rec["status"] = "launch_failed"
    return rec


# ---------- 入口 ----------
def do_check():
    global ADB
    ADB = find_adb()
    ok(f"adb：{ADB}")
    pick_device()
    ensure_root()
    ensure_network()
    ensure_frida_server()
    ensure_module_apk()
    ensure_vending()
    try:
        import frida
        ok(f"frida：{frida.__version__}")
    except Exception:
        warn("电脑没装 frida，请执行：pip3 install frida")
    ok("环境自检通过，可以开始跑号了")
    return 0


def parse_accounts(path: Path):
    """每行：邮箱----密码----辅助邮箱----2FA----卡号----有效期----CVC----持卡人----邮编"""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("----")]
        while len(parts) < 9:
            parts.append("")
        rows.append(parts[:9])
    return rows


def parse_card(parts) -> dict | None:
    """从账号行里取卡信息（第 5~9 项）。"""
    if len(parts) < 5 or not parts[4]:
        return None
    return {
        "number": re.sub(r"\s+", "", parts[4]),
        "exp": parts[5] or "",
        "cvc": parts[6] or "",
        "holder": parts[7] or "",
        "zip": parts[8] or "97201",
    }


def main():
    global ADB, SERIAL
    ap = argparse.ArgumentParser(description="Google AI Ultra 0 元开通一键脚本")
    ap.add_argument("accounts", nargs="?", help="账号文件（每行 email----password----recovery----totp）")
    ap.add_argument("--account", help="单号：email:password:totp")
    ap.add_argument("--check", action="store_true", help="只做环境自检")
    ap.add_argument("--list", action="store_true", help="只列出 offer 和 token，不拉起收银台（零风险）")
    ap.add_argument("--force", action="store_true", help="跳过 Play 账号校验（读不到账号时用）")
    ap.add_argument("--mode", type=int, default=None,
                    help="替换模式：1=TIME_PRORATION 2=CHARGE_PRORATED_PRICE 3=WITHOUT_PRORATION 4=DEFERRED 5=CHARGE_FULL_PRICE")
    ap.add_argument("--old-token", default="",
                    help="当前订阅的 purchaseToken（配合 --stack，直接用它做升级，跳过 queryPurchases）")
    ap.add_argument("--stack", action="store_true",
                    help="订阅升级叠加：用旧 purchaseToken + CHARGE_FULL_PRICE 拉起结算，剩余试用期会折算顺延")
    ap.add_argument("--serial", default=None)
    ap.add_argument("--no-add", action="store_true", help="跳过自动加号（账号已在手机上）")
    ap.add_argument("--no-switch", action="store_true",
                    help="不自动切号，只校验当前 Play 账号是否为目标号")
    ap.add_argument("--plan", default="auto", choices=["auto", "5x", "20x", "pro12", "pro6", "pro6b", "pro6c"],
                    help="auto=两档都查挑最长；5x=Ultra 20TB；20x=Ultra 30TB")
    a = ap.parse_args()

    ADB = find_adb()
    globals()["SKIP_ACCOUNT_CHECK"] = bool(a.force)
    if a.check:
        return do_check()

    pick_device()
    if a.serial:
        SERIAL = a.serial
    ensure_root()
    ensure_network()
    ensure_frida_server()
    ensure_module_apk()
    ensure_vending()   # Play 商店必须在跑，否则计费查询永远不回调

    REPORT_DIR.mkdir(exist_ok=True)
    rows = []
    if a.list and not a.account and not a.accounts:
        a.account = "current@device"
    if a.account:
        parts = a.account.split(":")
        rows = [[parts[0], parts[1] if len(parts) > 1 else "", "", parts[2] if len(parts) > 2 else ""]]
    elif a.accounts:
        rows = parse_accounts(Path(a.accounts))
    else:
        ap.print_help()
        return 1

    print(f"\n共 {len(rows)} 个账号，开始执行\n")
    results = []
    for i, row in enumerate(rows, 1):
        email, pw, _rec, sec = row[0], row[1], row[2], row[3]
        card = parse_card(row)
        print(f"\n──── 进度 {i}/{len(rows)} ────")
        try:
            rec = process(email, pw, sec, add=(not a.no_add and not a.list), card=card, plan=a.plan,
                          no_switch=a.no_switch, list_only=a.list, stack=a.stack, old_token=a.old_token,
                          stack_mode=a.mode)
        except Exception as e:
            rec = {"email": email, "status": "exception", "error": str(e)[:200]}
        results.append(rec)
        (REPORT_DIR / f"{email.split('@')[0]}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   结果：{rec.get('status')}")

    print("\n" + "=" * 56)
    print("  汇总")
    print("=" * 56)
    for r in results:
        print(f"  {r['email']:<42} {r.get('status')}")
    print(f"\n明细已保存到 {REPORT_DIR.resolve()}")
    return 0


entry = main


# The original embedded resources are separate files for inspection.
_RESOURCE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
FRIDA_JS = (_RESOURCE_DIR / 'billing.js').read_text(encoding='utf-8')
MODULE_B64 = base64.b64encode((_RESOURCE_DIR / 'billing-module.apk').read_bytes()).decode('ascii')

if __name__ == '__main__':
    sys.exit(entry())

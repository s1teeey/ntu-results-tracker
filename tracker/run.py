#!/usr/bin/env python3
"""NTU results tracker: poll for the 甄試 榜單, publish status to the repo (data/status.json),
then parse the 榜單 and publish data/outcomes.json.  Self-contained: needs git (pushable clone),
curl, pdftotext, python3.

usage: run.py --repo <clone dir> --batch 2 --deadline <epoch> [--hb 300] [--branch main] [--no-push]
stdout (one line per event): START | PUSHED <what> | FOUND <url> | DONE valid=<bool> | MINE ... | DEADLINE
"""
import argparse, datetime, json, os, re, subprocess, sys, time, urllib.parse

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True); ap.add_argument("--batch", default="2")
ap.add_argument("--deadline", type=float, required=True); ap.add_argument("--hb", type=float, default=300)
ap.add_argument("--branch", default="main"); ap.add_argument("--no-push", action="store_true")
ap.add_argument("--test-url", default=""); ap.add_argument("--year", default="116"); ap.add_argument("--index-sleep", type=float, default=10)
a = ap.parse_args()

HOST = "https://www.aca.ntu.edu.tw"
IDX = HOST + "/w/aca/LocalAdmissionClass_21072014105459968"
N, Y = a.batch, a.year
TARGET = f"{Y}碩士班甄試招生第{N}梯次"
names = [f"放榜用-{Y}第{N}梯次電子榜單.pdf",
         f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1119.pdf",
         f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1120.pdf",
         f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單.pdf",
         f"國立臺灣大學{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單.pdf",
         f"國立臺灣大學{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1119.pdf",
         f"{Y}學年度碩甄第{N}梯次電子榜單.pdf",
         f"{Y}碩士班甄試第{N}梯次正備取生名單.pdf",
         f"錄取名單-{Y}碩甄第{'二' if N == '2' else '一'}梯次.pdf"]
cands = [f"{HOST}/WebUPD/aca/{d}/" + urllib.parse.quote(n) for d in ("LocalAdmissionClass", "A02") for n in names]
here = os.path.dirname(os.path.abspath(__file__))
iso = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run(cmd, timeout=120, cwd=None):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return r.returncode, (r.stdout + r.stderr)
    except Exception as e:
        return 1, str(e)

def probe(u):
    try:
        o = subprocess.run(["curl", "-sS", "-m", "12", "-A", "Mozilla/5.0", "-r", "0-99", "-o", "/dev/null", "-w",
                            "%{http_code} %{content_type}", u], capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return False
    return o.startswith(("200", "206")) and "pdf" in o.lower()

def index_hit():
    try:
        h = subprocess.run(["curl", "-sS", "-m", "15", "-A", "Mozilla/5.0", "-L", IDX], capture_output=True, text=True, timeout=25).stdout
    except Exception:
        return None
    m = re.search(r'href="([^"]+)"[^>]*>\s*' + re.escape(TARGET), h)
    return urllib.parse.urljoin(IDX, m.group(1)) if m else None

# ---------- repo publishing ----------
def git(*args, timeout=120):
    return run(["git", "-c", "user.name=tracker-bot", "-c", "user.email=noreply@users.noreply.github.com", *args], timeout, a.repo)

def publish(files, msg):
    """files: {relative path: text}. Always rebuilds on the latest remote so there are never conflicts."""
    for rel, text in files.items():
        p = os.path.join(a.repo, rel); os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w", encoding="utf-8").write(text)
    if a.no_push:
        print("PUSHED (dry) " + msg, flush=True); return True
    for attempt in range(5):
        git("add", *files.keys())
        rc, out = git("commit", "-m", msg)
        if rc != 0 and "nothing to commit" in out: return True
        rc, out = git("push", "origin", f"HEAD:refs/heads/{a.branch}", timeout=180)
        if rc == 0:
            print("PUSHED " + msg, flush=True); return True
        # remote moved: rebuild on the latest remote, re-apply our files, retry
        git("fetch", "--depth=1", "origin", a.branch, timeout=180)
        git("reset", "--hard", "FETCH_HEAD")
        for rel, text in files.items():
            open(os.path.join(a.repo, rel), "w", encoding="utf-8").write(text)
        time.sleep(2 ** attempt)
    print("PUSH FAILED " + msg, flush=True); return False

# ---------- status ----------
sp = os.path.join(a.repo, "data", "status.json")
try: S = json.load(open(sp, encoding="utf-8"))
except Exception: S = {}
S.setdefault("log", [])
def log(msg): S["log"] = (S["log"] + [{"ts": iso(), "msg": msg}])[-40:]
def push_status(msg): return publish({"data/status.json": json.dumps(S, ensure_ascii=False, separators=(",", ":"))}, msg)

S.update({"phase": "watching", "startedAt": iso(), "lastBeatAt": iso(), "checks": S.get("checks", 0) if S.get("phase") == "watching" else 0,
          "note": "", "foundAt": None, "url": None})
log("工作已啟動，開始每 10 秒檢查教務處頁面")
print("START " + iso(), flush=True)
push_status("status: started")

checks = S["checks"]; i = 0; last_hb = time.time(); found = (a.test_url, "test") if a.test_url else None
while not found and time.time() < a.deadline:
    u = index_hit(); checks += 1
    if u: found = (u, "index page"); break
    if i % 3 == 0:
        for c in cands:
            if probe(c): found = (c, "direct file probe"); break
        if found: break
    i += 1
    if time.time() - last_hb >= a.hb:
        S["lastBeatAt"] = iso(); S["checks"] = checks; log(f"仍在追蹤，已檢查 {checks} 次，尚未放榜")
        push_status("status: heartbeat"); last_hb = time.time()
    time.sleep(a.index_sleep)

if not found:
    S.update({"phase": "timeout", "lastBeatAt": iso(), "checks": checks}); log("到截止時間仍未看到榜單")
    push_status("status: timeout"); print("DEADLINE " + iso(), flush=True); sys.exit(2)

url = found[0].replace("http://", "https://")
pu = urllib.parse.urlsplit(url); url = urllib.parse.urlunsplit((pu.scheme, pu.netloc, urllib.parse.quote(urllib.parse.unquote(pu.path)), "", ""))
S.update({"phase": "found", "lastBeatAt": iso(), "checks": checks, "foundAt": iso(), "url": url}); log("榜單已出現，正在解析")
print("FOUND " + url + f" ({found[1]})", flush=True)
push_status("status: FOUND")            # the page pops up its 已放榜 dialog as soon as this lands

# ---------- parse + publish outcomes ----------
work = os.path.join(a.repo, "_work"); os.makedirs(work, exist_ok=True)
pdf, txt, out = os.path.join(work, "r.pdf"), os.path.join(work, "r.txt"), os.path.join(work, "outcomes.json")
ok = False
for _ in range(3):
    rc, o = run(["curl", "-sS", "-m", "90", "-A", "Mozilla/5.0", "-o", pdf, url], 120)
    if rc == 0 and os.path.getsize(pdf) > 10000: ok = True; break
    time.sleep(5)
valid = False
if ok:
    run(["pdftotext", "-layout", pdf, txt], 120)
    rc, o = run([sys.executable, os.path.join(here, "extract_all.py"), txt, os.path.join(a.repo, "data", "roster.json"), out, url, S["foundAt"]], 120)
    print(o.strip(), flush=True)
    if os.path.exists(out):
        text = open(out, encoding="utf-8").read(); valid = bool(json.loads(text).get("valid"))
        publish({"data/outcomes.json": text}, "outcomes: " + ("valid" if valid else "INVALID"))
else:
    print("PDF download failed", flush=True)
S.update({"lastBeatAt": iso()}); log("榜單解析完成" if valid else "榜單已抓到，但名冊核對未通過或解析失敗")
push_status("status: done")
subprocess.run(["rm", "-rf", work])
print(f"DONE valid={valid}", flush=True)

#!/usr/bin/env python3
"""Guess the results-file URL directly, every few seconds, without waiting for the index page.

Probes the same candidate file names the tracker uses (plus the wider variants) in ONE parallel curl call per
cycle (HTTP HEAD, connection reuse). On the first PDF hit it can hand over to tracker/run.py (--test-url) so the
usual FOUND/outcomes files get pushed to the repo.

usage: guess.py --repo <clone> [--batch 2] [--every 5] [--deadline <epoch>] [--dirs LocalAdmissionClass,A02]
                [--no-pipeline] [--include-control]
stdout: START / CYCLE <n> ... (about once a minute) / HIT <url> / PIPELINE ... / DEADLINE
"""
import argparse, datetime, os, subprocess, sys, time, urllib.parse

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True); ap.add_argument("--batch", default="2"); ap.add_argument("--year", default="116")
ap.add_argument("--every", type=float, default=5.0); ap.add_argument("--deadline", type=float, default=0)
ap.add_argument("--dirs", default="LocalAdmissionClass,A02"); ap.add_argument("--max-time", type=int, default=8)
ap.add_argument("--parallel", type=int, default=10); ap.add_argument("--no-pipeline", action="store_true")
ap.add_argument("--include-control", action="store_true", help="also probe the batch-1 file (it exists) to prove detection works")
a = ap.parse_args()
Y, N = a.year, a.batch
HOST = "https://www.aca.ntu.edu.tw/WebUPD/aca/"
zh = {"1": "一", "2": "二"}[N]
names = [f"放榜用-{Y}第{N}梯次電子榜單", f"放榜用-{Y}第{zh}梯次電子榜單", f"放榜用-{Y}碩士班甄試第{N}梯次電子榜單",
         f"放榜用-{Y}第{N}梯次電子榜單(1)", f"放榜用-{Y}第{N}梯次電子榜單_1", f"放榜用-{Y}學年度第{N}梯次電子榜單",
         f"放榜用-{Y}第{N}梯次電子榜單0", f"放榜用-{Y}第{N}梯次", f"{Y}第{N}梯次電子榜單",
         f"{Y}學年度碩甄第{N}梯次電子榜單", f"{Y}學年度碩甄第{zh}梯次電子榜單",
         f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單", f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1118",
         f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1119", f"{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1120",
         f"國立臺灣大學{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單", f"國立臺灣大學{Y}學年度碩士班甄試招生第{N}梯次正、備取生名單1119",
         f"{Y}碩士班甄試第{N}梯次正備取生名單", f"{Y}碩士班甄試招生第{N}梯次正備取生名單", f"{Y}碩甄第{N}梯次正備取生名單",
         f"錄取名單-{Y}碩甄第{zh}梯次", f"錄取名單-{Y}碩甄第{N}梯次",
         f"{Y}學年度碩士班甄試招生第{N}梯次放榜正、備取生名單", f"{Y}碩士班招生第{N}梯次放榜正、備取生名單",
         f"{Y}學年度碩士班甄試第{N}梯次正、備取生名單", f"放榜用-{Y}第{N}梯次正備取榜單", f"{Y}第{N}梯次放榜榜單"]
if a.include_control: names.append(f"放榜用-{Y}第1梯次電子榜單")
dirs = [d for d in a.dirs.split(",") if d]
urls = [HOST + d + "/" + urllib.parse.quote(n + ".pdf") for d in dirs for n in names]
iso = lambda: datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S")

def cycle():
    """One HEAD per URL in a single parallel curl call. Returns (hit_url_or_None, counts)."""
    try:
        out = subprocess.run(["curl", "-sS", "--parallel", "--parallel-max", str(a.parallel)] + sum(
            [["-I", "-o", "/dev/null", "--max-time", str(a.max_time), "-A", "Mozilla/5.0", "-w", "%{url_effective} %{http_code} %{content_type}\n", u, "--next"] for u in urls], [])[:-1],
            capture_output=True, text=True, timeout=a.max_time * 3 + 10).stdout
    except Exception:
        return None, {"err": len(urls)}
    counts, hit = {}, None
    for line in out.splitlines():
        parts = line.rsplit(" ", 2)
        if len(parts) < 3: continue
        u, code, ctype = parts[0], parts[1], parts[2]
        counts[code] = counts.get(code, 0) + 1
        if code in ("200", "206") and "pdf" in ctype.lower() and hit is None: hit = u
    counts["missing"] = len(urls) - sum(counts.values())
    return hit, counts

def verify_pdf(u):
    try:
        b = subprocess.run(["curl", "-sS", "-m", "20", "-A", "Mozilla/5.0", "-r", "0-4", u], capture_output=True, timeout=30).stdout
        return b.startswith(b"%PDF")
    except Exception:
        return False

print(f"START {iso()}Z probing {len(urls)} urls every {a.every:g}s (dirs={dirs})", flush=True)
n = 0
while True:
    t0 = time.time()
    if a.deadline and t0 > a.deadline:
        print(f"DEADLINE {iso()}Z", flush=True); sys.exit(2)
    n += 1
    hit, counts = cycle()
    if hit and verify_pdf(hit):
        print(f"HIT {hit}", flush=True)
        if a.no_pipeline: sys.exit(0)
        r = subprocess.run(["git", "-C", a.repo, "fetch", "-q", "--depth=1", "origin", "main"], capture_output=True)
        subprocess.run(["git", "-C", a.repo, "reset", "-q", "--hard", "FETCH_HEAD"], capture_output=True)
        print("PIPELINE start (run.py --test-url)", flush=True)
        p = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py"), "--repo", a.repo,
                            "--batch", N, "--deadline", str(time.time() + 120), "--test-url", hit], capture_output=True, text=True)
        print("PIPELINE output:\n" + p.stdout[-1500:], flush=True); sys.exit(0)
    if n == 1 or n % 12 == 0:
        print(f"CYCLE {n} {iso()}Z codes={counts}", flush=True)
    time.sleep(max(0.0, a.every - (time.time() - t0)))

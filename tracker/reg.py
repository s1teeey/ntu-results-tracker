#!/usr/bin/env python3
"""Snapshot NTU's 正備取 網路報到 status for 商研/國企/財金甲乙丙 into data/reg.json.

usage: python3 tracker/reg.py [out.json]
Source: https://gra108.aca.ntu.edu.tw/regchk/stu_query.asp (public query page).
Also computes, from the snapshot alone, the guaranteed (至少) and best-case (至多) 備取 reach per department:
  至少: only 已放棄, and 志願k people whose better choice is a 正取 or a 備取 already guaranteed, free a seat;
  至多: also every 未報到 and every 志願2+ person leaves.
A masked name is treated as one person only if its statuses are consistent (all reported or none; distinct 志願;
志願1 正取 means everything else is 已放棄)."""
import collections, datetime, html, json, re, sys, urllib.parse, urllib.request

URL = "https://gra108.aca.ntu.edu.tw/regchk/stu_query.asp"
DEPTS = [("7010", "商研"), ("7070", "國企"), ("7040", "財金甲"), ("7050", "財金乙"), ("7060", "財金丙")]

def get(data=None):
    req = urllib.request.Request(URL, data=data, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r: return r.read().decode("utf-8", "replace")

def cells(row): return [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]

def fetch():
    opts = [html.unescape(v) for v in re.findall(r"<option value='([^']*)'", get())]
    D = {}
    for code, _ in DEPTS:
        v = [o for o in opts if o.startswith(code)][0]
        page = get(urllib.parse.urlencode({"DEP": v, "qry": "查詢"}).encode())
        rows = []
        for r in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
            c = cells(r)
            if len(c) >= 6 and re.match(r"[A-Z\d]\d{6}$", c[1]):
                m = re.match(r"(正取|備取)\s*(\d+)-(\d+)", c[3])
                rows.append({"id": c[1], "n": c[2], "t": "W" if m.group(1) == "正取" else "B", "r": int(m.group(2)), "s": int(m.group(3)), "st": c[4], "sub": c[5]})
        if not rows: raise SystemExit(f"{code}: no rows")
        D[code] = rows
    return D

def analyse(D):
    P = collections.defaultdict(dict)
    for d in D:
        for r in D[d]: P[r["n"]][d] = r
    def same(n):
        e = P[n]; st = [r["st"] for r in e.values()]
        if len(e) < 2: return False
        if "未報到" in st and any(s != "未報到" for s in st): return False
        v = [s for s in st if s.startswith("志願")]
        if len(v) != len(set(v)): return False
        for d, r in e.items():
            if r["st"] == "志願1" and r["t"] == "W" and any(x["st"] != "已放棄" for dd, x in e.items() if dd != d): return False
        return True
    link = {n: same(n) for n in P}
    def walk(gone, reach):
        out = {}
        for d in D:
            win = [r for r in D[d] if r["t"] == "W"]; wait = [r for r in D[d] if r["t"] == "B"]
            free = sum(1 for r in win if gone(d, r, reach)); f = free; last = 0
            for i, r in enumerate(wait, 1):
                if f <= 0: break
                if gone(d, r, reach): continue
                f -= 1; last = i
            out[d] = {"free": free, "reach": last, "all": f > 0}
        return out
    def g_min(d, r, reach):
        if r["st"] == "已放棄": return True
        if not r["st"].startswith("志願") or not link[r["n"]]: return False
        k = int(r["st"][2:])
        for dd, x in P[r["n"]].items():
            if dd == d or not x["st"].startswith("志願") or int(x["st"][2:]) >= k: continue
            if x["t"] == "W": return True
            pos = [y["id"] for y in D[dd] if y["t"] == "B"].index(x["id"]) + 1
            if pos <= reach.get(dd, {}).get("reach", 0): return True
        return False
    reach = {}
    for _ in range(10):
        new = walk(g_min, reach)
        if new == reach: break
        reach = new
    g_max = lambda d, r, _: r["st"] in ("已放棄", "未報到") or (r["st"].startswith("志願") and int(r["st"][2:]) > 1)
    hi = walk(g_max, {})
    return {d: {"min": reach[d], "max": hi[d]} for d in D}, {n: v for n, v in link.items() if v}

def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "data/reg.json"
    D = fetch(); est, linked = analyse(D)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    res = {"at": now, "deadline": "2026-11-26T24:00:00+08:00", "source": URL,
           "depts": [{"code": c, "name": n, "rows": D[c], "est": est[c]} for c, n in DEPTS], "linked": sorted(linked)}
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    for c, n in DEPTS:
        cnt = collections.Counter("志願" if r["st"].startswith("志願") else r["st"] for r in D[c] if r["t"] == "W")
        e = est[c]
        print(f"{n}: 正取 {dict(cnt)} | 至少到備取第{e['min']['reach']}位 至多到第{e['max']['reach']}位{'（用完）' if e['max']['all'] else ''}")

if __name__ == "__main__":
    main()

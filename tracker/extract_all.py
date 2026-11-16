#!/usr/bin/env python3
"""usage: extract_all.py <result.txt> <roster.json|-> <out.json> [url] [foundAt]
Parses the 一般生 正取/備取 lists of 商研所(7010), 國企(7070), 財金甲/乙/丙(7040/7050/7060) from a
pdftotext -layout dump of the NTU 甄試 榜單, validates them, and writes out.json for the status page."""
import re, sys, json
txt = open(sys.argv[1], encoding="utf-8").read()
roster = None if sys.argv[2] == "-" else json.load(open(sys.argv[2], encoding="utf-8"))
if roster and "people" not in roster and isinstance(roster.get("data"), dict): roster = roster["data"]  # db export wrapper
out_path = sys.argv[3]; url = sys.argv[4] if len(sys.argv) > 4 else ""; found_at = sys.argv[5] if len(sys.argv) > 5 else ""
CODES = {"7010": "商研所", "7070": "國企", "7040": "財金甲", "7050": "財金乙", "7060": "財金丙"}
sec, declared, reasons = {}, {}, []
for blk in re.split(r"系所組別：", txt)[1:]:
    for code in CODES:
        if "身分別：一般生" not in blk[:120]: continue
        rows = re.findall(r"^\s*(" + code + r"\d{3})\s+(.+?)\s+(正取|備取)\s*$", blk, re.M)
        if not rows: continue
        sec[code] = {"win": [r[0] for r in rows if r[2] == "正取"], "wait": [r[0] for r in rows if r[2] == "備取"]}
        m = re.search(r"以上合計錄取[:：]\s*正取\s*(\d+)\s*名(?:\s*備取\s*(\d+)\s*名)?", blk)
        declared[code] = [int(m.group(1)), int(m.group(2) or 0)] if m else None
for code, name in CODES.items():
    if code not in sec: reasons.append(f"{name}：找不到一般生名單"); continue
    d = declared.get(code); got = [len(sec[code]["win"]), len(sec[code]["wait"])]
    if d is None: reasons.append(f"{name}：找不到榜單合計人數，無法核對")
    elif d != got: reasons.append(f"{name}：解析 正取{got[0]}/備取{got[1]}，榜單合計 正取{d[0]}/備取{d[1]}")
if roster:
    ids = {"7010": [p["b"] for p in roster["people"] if p.get("b") and not p.get("babs")],
           "7070": [p["i"] for p in roster["people"] if p.get("i")]}
    for code, lst in ids.items():
        if code in sec:
            listed = set(sec[code]["win"]) | set(sec[code]["wait"])
            cov = sum(1 for i in lst if str(i) in listed) / max(1, len(lst))
            if cov < 0.3: reasons.append(f"{CODES[code]}：名冊准考證只有 {cov:.0%} 出現在榜單，可能是不同年度或格式變了")
res = {"valid": not reasons, "reasons": reasons, "foundAt": found_at, "url": url, "sec": sec,
       "declared": {k: v for k, v in declared.items() if v}}
json.dump(res, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
print("VALID" if res["valid"] else "INVALID: " + "; ".join(reasons))
for code, name in CODES.items():
    if code in sec: print(f"  {name}: 正取{len(sec[code]['win'])} 備取{len(sec[code]['wait'])} (榜單合計 {declared.get(code)})")
for label, mid, code in (("商研所", "7010069", "7010"), ("國企", "7070076", "7070")):
    s = sec.get(code)
    if not s: print(f"MINE {label} {mid}: 讀取失敗"); continue
    out = "正取" if mid in s["win"] else (f"備取第{s['wait'].index(mid)+1}順位" if mid in s["wait"] else "未列入榜單")
    print(f"MINE {label} {mid}: {out}")

#!/usr/bin/env python3
"""口述→口播稿的机械检查：原话保留、数字锚点、句长、规避话术、AI 腔、口头禅残留、时长估算。

只提供候选证据，不做语义判断；error 必须改或写明理由，warn 由作者决定。
用法：python3 check_oral_script.py --oral 口述.txt --script 口播稿.md [--mode polish|rewrite] [--json]
"""
import argparse, json, re, sys

MARKUP = [r"\[画面[:：][^\]]*\]", r"\[补[^\]]*\]", r"\[锁\]", r"\*\*", r"／", r"^#+.*$", r"^>.*$", r"^\s*[-|].*$"]
HEDGES = ["待核验", "以实际为准", "仅供参考", "不能保证", "这只能证明", "具体以官方为准"]
AI_TONE = ["赋能", "助力", "值得一提的是", "总而言之", "综上所述", "让我们", "家人们", "干货满满", "不得不说", "众所周知", "在这个时代", "一起来看看"]
FILLERS = ["然后", "就是说", "那个", "嗯", "对吧", "其实"]
NUM = re.compile(r"[0-9０-９][0-9０-９.,，]*[万千百亿%]?|[一二两三四五六七八九十百千万亿半]+(?=[个块元天周月年小分秒字条次倍人期款遍])")
MIN_KEEP = {"polish": 0.55, "rewrite": 0.30}
CHARS_PER_SEC = 4.5  # 中文口播常速，约 270 字/分钟


def clean_script(text):
    lines = []
    for line in text.splitlines():
        for pat in MARKUP:
            line = re.sub(pat, "", line)
        if line.strip():
            lines.append(line.strip())
    return "\n".join(lines)


def han(text):
    return re.sub(r"[^\u4e00-\u9fff0-9A-Za-z]", "", text)


def keep_ratio(oral, script, n=4):
    """稿子里有多少字落在与口述共有的 n 字片段内。"""
    o, s = han(oral), han(script)
    if len(s) < n:
        return 1.0
    grams = {o[i:i + n] for i in range(len(o) - n + 1)}
    covered = [False] * len(s)
    for i in range(len(s) - n + 1):
        if s[i:i + n] in grams:
            for j in range(i, i + n):
                covered[j] = True
    return sum(covered) / len(s)


def sentences(script):
    parts = re.split(r"[。！？!?\n]+", script)
    return [p.strip(" ，,：:") for p in parts if han(p)]


def check(oral, script_raw, mode="polish"):
    script = clean_script(script_raw)
    issues = []
    ratio = keep_ratio(oral, script)
    if ratio < MIN_KEEP[mode]:
        issues.append({"level": "error", "rule": "原话保留", "detail": f"保留率 {ratio:.0%} 低于 {MIN_KEEP[mode]:.0%}（{mode}）；是否换成了助手自己的话？"})
    oral_nums = set(NUM.findall(oral))
    script_nums = set(NUM.findall(script))
    for n in sorted(script_nums - oral_nums):
        if n not in oral:
            issues.append({"level": "warn", "rule": "新增数字", "detail": f"稿中“{n}”在口述里找不到；确认来自作者或已核验，否则删掉"})
    for n in sorted(oral_nums - script_nums):
        if n not in script:
            issues.append({"level": "warn", "rule": "数字丢失", "detail": f"口述里的“{n}”没进稿；是有意删掉吗？"})
    sents = sentences(script)
    for s in sents:
        L = len(han(s))
        if L > 30:
            issues.append({"level": "error", "rule": "句长", "detail": f"{L} 字：{s[:24]}…（>30，拆开）"})
    long20 = sum(1 for s in sents if 20 < len(han(s)) <= 30)
    if sents and long20 / len(sents) > 0.3:
        issues.append({"level": "warn", "rule": "句长", "detail": f"{long20}/{len(sents)} 句在 21–30 字，节奏偏慢"})
    for w in HEDGES:
        if w in script and w not in oral:
            issues.append({"level": "error", "rule": "规避话术", "detail": f"“{w}”不是作者说的，删掉"})
    for w in AI_TONE:
        if w in script and w not in oral:
            issues.append({"level": "warn", "rule": "AI 腔", "detail": f"“{w}”"})
    body = han(script)
    filler = sum(script.count(w) for w in FILLERS)
    if body and filler / len(body) * 100 > 1.0:
        issues.append({"level": "warn", "rule": "口头禅残留", "detail": f"每百字 {filler / len(body) * 100:.1f} 个（然后/就是说/那个/嗯/对吧/其实）"})
    stats = {"keep_ratio": round(ratio, 3), "sentences": len(sents), "chars": len(body),
             "est_seconds": round(len(body) / CHARS_PER_SEC), "est_seconds_at_1.13x": round(len(body) / CHARS_PER_SEC / 1.13)}
    return {"ok": not any(i["level"] == "error" for i in issues), "stats": stats, "issues": issues}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oral", required=True)
    ap.add_argument("--script", required=True)
    ap.add_argument("--mode", choices=list(MIN_KEEP), default="polish")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = check(open(a.oral, encoding="utf-8").read(), open(a.script, encoding="utf-8").read(), a.mode)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        s = r["stats"]
        print(f"{'通过' if r['ok'] else '未通过'} | 保留率 {s['keep_ratio']:.0%} | {s['sentences']} 句 {s['chars']} 字 | 约 {s['est_seconds']}s（1.13x 约 {s['est_seconds_at_1.13x']}s）")
        for i in r["issues"]:
            print(f"[{i['level']}] {i['rule']}：{i['detail']}")
    sys.exit(0 if r["ok"] else 1)


if __name__ == "__main__":
    main()

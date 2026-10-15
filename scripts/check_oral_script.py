#!/usr/bin/env python3
"""口述→口播稿的机械检查：原话保留、数字锚点、句长、规避话术、AI 腔、口头禅残留、时长估算。

只提供候选证据，不做语义判断；error 必须改或写明理由，warn 由作者决定。
用法：python3 check_oral_script.py --oral 口述.txt --script 口播稿.md [--mode polish|rewrite|expand] [--json]
模式：polish 润色（默认）；rewrite 重写；expand 大纲扩写+纠错（作者只给要点，助手找材料扩写）。
"""
import argparse, json, re, sys

MARKUP = [r"\[画面[:：][^\]]*\]", r"\[补[^\]]*\]", r"\[改[^\]]*\]", r"\[锁\]", r"\*\*", r"／", r"^#+.*$", r"^>.*$", r"^\s*[-|].*$"]
HEDGES = ["待核验", "以实际为准", "仅供参考", "不能保证", "这只能证明", "具体以官方为准"]
AI_TONE = ["赋能", "助力", "值得一提的是", "总而言之", "综上所述", "让我们", "家人们", "干货满满", "不得不说", "众所周知", "在这个时代", "一起来看看"]
ANNOUNCE = re.compile(r"第[一二三四五六七八九十]+个(岔口|问题|阶段|部分|环节)[：:]|一句话总结|接下来我们|下面我们来|首先[^。]*其次|最后我们来")
PREACH = ["不丢人", "这就是很多人的误区", "你要知道", "记住", "请记住", "说到底", "归根结底"]
FILLERS = ["然后", "就是说", "那个", "嗯", "对吧", "其实"]
NUM = re.compile(r"[0-9０-９][0-9０-９.,，]*[万千百亿%]?|[一二两三四五六七八九十百千万亿半]+(?=[个块元天周月年小分秒字条次倍人期款遍])")
MIN_KEEP = {"polish": 0.55, "rewrite": 0.30, "expand": 0.15}
BREATH_MAX = 20   # 一口气（逗号、／之间）的最大音节当量
LINE_MAX = 40     # 一整句的最大音节当量
LATIN_WORD = 2    # 一个英文词/数字串约等于 2 个汉字的念读时长
CHARS_PER_SEC = 4.5  # 中文口播常速，约 270 字/分钟


def numbers(text):
    """抽取数字锚点；单个汉字数字（第三个、两点）多为序数或量词，不算锚点。"""
    out = set()
    for n in NUM.findall(text):
        if re.fullmatch(r"[一二两三四五六七八九十半]", n):
            continue
        out.add(n)
    return out


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


def units(text):
    """念读长度：汉字算 1，英文词或数字串算 LATIN_WORD。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff]", text))
    latin = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9.\-]*", text))
    return cjk + latin * LATIN_WORD


def breaths(sentence):
    return [b for b in re.split(r"[，,、；;：:／/—]+", sentence) if han(b)]


def tagged_numbers(script_raw):
    """带 [补…] 或 [改…] 标记的行里的数字视为已声明来源的补充。"""
    nums = set()
    for line in script_raw.splitlines():
        if re.search(r"\[(补|改)", line):
            nums |= numbers(clean_script(line))
    return nums


def check(oral, script_raw, mode="polish"):
    script = clean_script(script_raw)
    issues = []
    ratio = keep_ratio(oral, script)
    if ratio < MIN_KEEP[mode]:
        issues.append({"level": "error", "rule": "原话保留", "detail": f"保留率 {ratio:.0%} 低于 {MIN_KEEP[mode]:.0%}（{mode}）；是否换成了助手自己的话？"})
    oral_nums = numbers(oral)
    script_nums = numbers(script)
    declared = tagged_numbers(script_raw)
    for n in sorted(script_nums - oral_nums - declared):
        if n not in oral:
            issues.append({"level": "warn", "rule": "新增数字", "detail": f"稿中“{n}”在口述里找不到；确认来自作者或已核验，否则删掉"})
    for n in sorted(oral_nums - script_nums):
        if n not in script:
            issues.append({"level": "warn", "rule": "数字丢失", "detail": f"口述里的“{n}”没进稿；是有意删掉吗？"})
    sents = sentences(script)
    for s in sents:
        L = units(s)
        if L > LINE_MAX:
            issues.append({"level": "error", "rule": "句长", "detail": f"整句约 {L} 字：{s[:24]}…（>{LINE_MAX}，拆成两句）"})
            continue
        for b in breaths(s):
            if units(b) > BREATH_MAX:
                issues.append({"level": "error", "rule": "气口", "detail": f"一口气约 {units(b)} 字：{b[:24]}…（>{BREATH_MAX}，加逗号或／）"})
    long_lines = sum(1 for s in sents if 28 < units(s) <= LINE_MAX)
    if sents and long_lines / len(sents) > 0.3:
        issues.append({"level": "warn", "rule": "句长", "detail": f"{long_lines}/{len(sents)} 句超过 28 字，节奏偏慢"})
    if mode == "expand" and not re.search(r"\[(补|改)", script_raw):
        issues.append({"level": "error", "rule": "扩写标记", "detail": "expand 模式必须用 [补:…]/[改:…] 标出补充和纠错"})
    for w in HEDGES:
        if w in script and w not in oral:
            issues.append({"level": "error", "rule": "规避话术", "detail": f"“{w}”不是作者说的，删掉"})
    for w in AI_TONE:
        if w in script and w not in oral:
            issues.append({"level": "warn", "rule": "AI 腔", "detail": f"“{w}”"})
    for m in sorted(set(x.group(0) for x in ANNOUNCE.finditer(script))):
        issues.append({"level": "warn", "rule": "报幕", "detail": f"“{m}”像讲课报幕；改用故事或问题过渡"})
    for w in PREACH:
        if w in script and w not in oral:
            issues.append({"level": "warn", "rule": "说教", "detail": f"“{w}”是助手加的判词/安慰；删掉或换成作者的经历"})
    body = han(script)
    spoken = units(script)
    filler = sum(script.count(w) for w in FILLERS)
    if body and filler / len(body) * 100 > 1.0:
        issues.append({"level": "warn", "rule": "口头禅残留", "detail": f"每百字 {filler / len(body) * 100:.1f} 个（然后/就是说/那个/嗯/对吧/其实）"})
    stats = {"keep_ratio": round(ratio, 3), "sentences": len(sents), "chars": len(body),
             "spoken_units": spoken, "est_seconds": round(spoken / CHARS_PER_SEC), "est_seconds_at_1.13x": round(spoken / CHARS_PER_SEC / 1.13)}
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

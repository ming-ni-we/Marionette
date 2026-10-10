"""自证扫描：emoji / 硬编码色值 / 紫→粉渐变 三项计数。
扫描范围：src/ 下所有 .ts .tsx（不含 .css，tokens.css 是唯一色值来源，单独说明）。
输出真实计数与命中明细，便于复核。
"""
import os
import re
import sys
import unicodedata

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
ROOT = os.path.normpath(ROOT)

CODE_EXT = (".ts", ".tsx")

# ---- emoji 判定：Unicode 码点区间（与任务书中给出的区间一致，并补充常见符号区）----
EMOJI_RANGES = [
    (0x1F300, 0x1F9FF),   # 杂项符号与象形、附加符号、扩展象形
    (0x2600, 0x26FF),     # 杂项符号
    (0x2700, 0x27BF),     # 装饰符号（含 dingbats）
    (0x1F000, 0x1F2FF),   # 麻将/多米诺/扑克/封闭表意
    (0x1FA70, 0x1FAFF),   # 符号与象形扩展-A
    (0x2B00, 0x2BFF),     # 杂项符号与箭头（含 ⭐ 等）
    (0xFE00, 0xFE0F),     # 变体选择符
    (0x1F1E6, 0x1F1FF),   # 区域指示符（国旗）
]


def is_emoji(ch: str) -> bool:
    cp = ord(ch)
    for lo, hi in EMOJI_RANGES:
        if lo <= cp <= hi:
            return True
    return False


# ---- 硬编码色值：hex 颜色，排除白名单 #fff / #ffffff / #000 / #000000（大小写与 3/6/8 位）----
HEX_RE = re.compile(r"#([0-9a-fA-F]{3,8})\b")
HEX_ALLOW = {"fff", "ffffff", "000", "000000", "FFFFFFFF", "00000000"}

# ---- 紫→粉渐变：同时出现 purple/violet/fuchsia/pink 的渐变类，或 from-* 与 to-* 命中近紫/粉 ----
PURPLE = r"(purple|violet|fuchsia|pink)"
GRAD_PURPLE_PINK = [
    re.compile(rf"from-{PURPLE}"),          # 任意 from-紫/粉
    re.compile(rf"to-{PURPLE}"),            # 任意 to-紫/粉
    re.compile(r"linear-gradient\([^)]*(purple|violet|fuchsia|pink)"),
]


def iter_files():
    for dirpath, _dirnames, filenames in os.walk(ROOT):
        for fn in filenames:
            if fn.endswith(CODE_EXT):
                yield os.path.join(dirpath, fn)


def main() -> int:
    emoji_hits = []
    hex_hits = []
    gradient_hits = []
    files = 0

    for path in iter_files():
        files += 1
        rel = os.path.relpath(path, ROOT)
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                for ch in line:
                    if is_emoji(ch):
                        emoji_hits.append((rel, lineno, ch, hex(ord(ch))))
                for m in HEX_RE.finditer(line):
                    token = m.group(1)
                    if token.lower() in HEX_ALLOW:
                        continue
                    # 排除 URL 锚点、正则片段等误报：要求前面不是字母数字（避免 xxx#fff 已排除）
                    hex_hits.append((rel, lineno, "#" + token))
                for rx in GRAD_PURPLE_PINK:
                    if rx.search(line):
                        gradient_hits.append((rel, lineno, line.strip()[:100]))

    print(f"[扫描范围] {ROOT}")
    print(f"[文件数]   {files} 个 .ts/.tsx")
    print(f"[1] emoji 字符数（U+1F300-1F9FF / 2600-26FF / 2700-27BF 等区间）: {len(emoji_hits)}")
    for h in emoji_hits[:50]:
        print("    ", h)
    print(f"[2] 硬编码 hex 色值（排除 #fff/#ffffff/#000/#000000）: {len(hex_hits)}")
    for h in hex_hits[:50]:
        print("    ", h)
    print(f"[3] 紫→粉渐变类/背景（from-*/to-*/linear-gradient 命中 purple/violet/fuchsia/pink）: {len(gradient_hits)}")
    for h in gradient_hits[:50]:
        print("    ", h)

    failed = bool(emoji_hits or hex_hits or gradient_hits)
    print("\n[结论]", "FAIL —— 存在命中项，见上" if failed else "PASS —— 三项均为 0")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

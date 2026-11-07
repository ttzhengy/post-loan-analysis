# ============================================================ 套话检测器


def _tokens(text):
    """切成中文词组（2-4 字滑窗）+ 数字，用于比较「措辞是否同质」"""
    text = re.sub(r"\s+", "", str(text))
    out = set()
    for seg in re.findall(r"[\u4e00-\u9fa5]+", text):
        n = len(seg)
        for L in (2, 3, 4):
            for i in range(max(0, n - L + 1)):
                out.add(seg[i:i + L])
    return out


def overlap_ratio(a, b):
    """两段文本的词集合 Jaccard 重叠度（0-1）"""
    A, B = _tokens(a), _tokens(b)
    if not A or not B:
        return 0.0
    return len(A & B) / max(1, min(len(A), len(B)))


def max_pair_overlap(texts):
    """一组文本里最相似的一对的词集合重叠度（最相似的一对决定「是不是套话」）"""
    best, pair = 0.0, ("", "")
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            r = overlap_ratio(texts[i], texts[j])
            if r > best:
                best, pair = r, (texts[i], texts[j])
    return best, pair


def jargon_report(nar, threshold=0.60):
    """套话体检：标题 / 决策动作 的最大两两重叠度。超过阈值即视为模板化"""
    titles = [t["title"] for t in nar.get("topics") or []]
    actions = [t["management_decision"]["action"] for t in nar.get("topics") or []]
    tr, tp = max_pair_overlap(titles)
    ar, ap = max_pair_overlap(actions)
    return {
        "title_overlap": round(tr, 3), "action_overlap": round(ar, 3),
        "title_pair": tp, "action_pair": ap,
        "threshold": threshold,
        "ok": bool(titles) and tr <= threshold and ar <= threshold,
        "distinct_titles": len(set(titles)) == len(titles),
        "distinct_actions": len(set(actions)) == len(actions),
    }

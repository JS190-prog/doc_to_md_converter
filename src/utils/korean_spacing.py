"""
Rule-based Korean spacing corrector for OCR post-processing.

Uses hangul jamo decomposition and common grammatical patterns
to insert missing spaces in OCR output where words are merged together.
"""

import re

# ---------------------------------------------------------------------------
# Hangul Unicode helpers
# ---------------------------------------------------------------------------
_HANGUL_BASE = 0xAC00
_HANGUL_END = 0xD7A3
_JONG_COUNT = 28


def _is_hangul(ch):
    return _HANGUL_BASE <= ord(ch) <= _HANGUL_END


def _jong_index(ch):
    """Return jongseong index (0 = no jongseong)."""
    if not _is_hangul(ch):
        return -1
    return (ord(ch) - _HANGUL_BASE) % _JONG_COUNT


def _has_jong(ch):
    return _jong_index(ch) > 0


# ---------------------------------------------------------------------------
# Space-insertion patterns (applied via regex)
# ---------------------------------------------------------------------------

def _build_patterns():
    """Build all regex patterns for Korean spacing correction."""
    patterns = []

    # ---- 1. Space after punctuation followed by Korean ----
    patterns.append((re.compile(r'([.!?])([가-힣])'), r'\1 \2'))
    patterns.append((re.compile(r'([,;])([가-힣])'), r'\1 \2'))

    # ---- 2. Space after closing quotes/brackets + Korean ----
    patterns.append((re.compile(r"([''\"»>\]])([가-힣])"), r'\1 \2'))

    # ---- 2b. Common adverbs: insert space AFTER when merged with next word ----
    adverbs = [
        '결국', '가장', '매우', '아주', '이미', '아직', '바로', '다시',
        '먼저', '모두', '항상', '자주', '특히', '또한', '결코', '과연',
        '그냥', '제일', '정말', '진짜', '너무', '상당히', '오히려',
        '여전히', '최근', '현재', '실제', '직접', '함께', '계속',
    ]
    adv_group = '|'.join(sorted(adverbs, key=len, reverse=True))
    patterns.append((
        re.compile(rf'(?<=[가-힣])({adv_group})([가-힣])'),
        r' \1 \2',
    ))

    # ---- 3. Number + specific Korean content words ----
    patterns.append((
        re.compile(r'(\d)(여성|남성|세대|시리즈|트렌드|인구|사람|소비자|직장인|여성들|남성들|세대의|여성은|남성은|여성이|남성이|여성을|남성을)'),
        r'\1 \2',
    ))

    # ---- 4. Korean word + 4-digit year ----
    patterns.append((re.compile(r'([가-힣])(\d{4}년)'), r'\1 \2'))
    # Korean word + number + %
    patterns.append((re.compile(r'([가-힣])(\d+%)'), r'\1 \2'))

    # ---- 5. Multi-char particles: insert space AFTER them ----
    # These are unambiguous multi-syllable particles/endings.
    multi_particles = [
        '에서', '까지', '부터', '으로', '처럼', '보다',
        '에게', '한테', '께서', '밖에',
        '으로서', '으로써', '에게서', '한테서',
    ]
    mp_group = '|'.join(sorted(multi_particles, key=len, reverse=True))
    # particle + hangul (not another particle-like char)
    patterns.append((
        re.compile(rf'([가-힣])({mp_group})([가-힣])'),
        r'\1\2 \3',
    ))

    # ---- 6. Verb/adjective endings: insert space AFTER ----
    # Common sentence-ending or clause-connecting patterns
    verb_endings = [
        # Sentence endings
        '이다', '였다', '었다', '했다', '됐다', '왔다', '갔다',
        '있다', '없다', '같다', '하다', '된다', '한다', '봤다',
        '니다', '습니다',
        # Clause connectors
        '인데', '지만', '해서', '므로', '니까', '라서', '면서',
        '하고', '되고', '하며', '되며', '해도', '서도',
        '하면', '되면',
        # Modifier (관형형) endings — space before the noun they modify
        '하는', '되는', '있는', '없는', '같은', '다른',
        '했던', '됐던', '있던', '없던',
        '다운', '적인', '로운',
        # ~ㄴ/은 modifier: 다양한, 새로운, 중요한, 핵심적인...
        '양한', '로운', '요한', '적인', '능한', '실한', '전한',
        '벽한', '분한', '확한', '숙한', '달한',
        # Noun-ending patterns
        '할수', '있는데', '없는데', '했는데', '됐는데',
        '라는', '라고', '라며', '라면',
    ]
    ve_group = '|'.join(sorted(verb_endings, key=len, reverse=True))
    patterns.append((
        re.compile(rf'({ve_group})([가-힣])'),
        r'\1 \2',
    ))

    # ---- 7. Single-char particles with jongseong check ----
    # These are handled separately in the jamo-aware function below.

    return patterns


_PATTERNS = _build_patterns()


# Exceptions: words where the "particle" is actually part of the word
# We'll check the 2-char substring ending with the particle
# These are common words that would be incorrectly split
_EXCEPTIONS_AFTER_JONG = {
    # 은: 은행, 은색, 은퇴, 은밀, 은혜
    '은': {'은행', '은색', '은퇴', '은밀', '은혜', '은근', '은하'},
    # 을: 을미, 을사 (rare)
    '을': set(),
    # 과: 과학, 과정, 과거, 과제, 과연, 과일, 과목
    '과': {'과학', '과정', '과거', '과제', '과연', '과일', '과목', '과감', '과도'},
    # 이: very common as part of words, so we skip single 이
}
_EXCEPTIONS_NO_JONG = {
    # 는: 는데 (keep together), but this is a connector not an exception
    '는': set(),
    # 를: rare as word-start
    '를': set(),
    # 와: 와중
    '와': {'와중'},
    # 가: 가능, 가격, 가치, 가정, 가족, 가운데, 가끔, 가까이
    # Note: 가장 removed — it's an adverb that should be separated
    '가': {'가능', '가격', '가치', '가정', '가족', '가운', '가끔', '가까', '가고', '가면', '가는', '가진', '가지', '가슴'},
}
_EXCEPTIONS_ANY = {
    # 의: 의미, 의견, 의식, 의무, 의도, 의료, 의사, 의외, 의지, 의하
    # Note: 의문 removed — "들의문제" should split as "들의 문제"
    # False positive "의문" handled by 3-char lookahead below
    '의': {'의미', '의견', '의식', '의무', '의도', '의료', '의사', '의외', '의지', '의원', '의존', '의하', '의해', '의류', '의석'},
    # 에: 에너, 에이 (에너지, 에이징)
    '에': {'에너', '에이', '에서'},
    # 도: 도서, 도시, 도움, 도전, 도구, 도달, 도입, 도대
    '도': {'도서', '도시', '도움', '도전', '도구', '도달', '도입', '도대', '도리', '도록', '도착', '도덕'},
}
# 3-char exception words: particle+2chars that form a real word
_EXCEPTIONS_3CHAR = {
    '의문이', '의문을', '의문의', '의문에', '의문점',
    '도움이', '도움을', '도움의', '도움에',
}
# Single-char particles that can ever trigger an insertion — anything else
# can be skipped without computing jongseong/lookahead.
_PARTICLE_CHARS = frozenset('은을과는를와의에도')


def _insert_spaces_after_single_particles(text):
    """
    Insert spaces after single-character particles using jongseong rules.

    받침 O + 은/을/과/이 → space after particle (if followed by hangul)
    받침 X + 는/를/와/가 → space after particle (if followed by hangul)
    Any   + 의/에/도     → space after particle (if followed by hangul)

    We must be careful of false positives (e.g., 의미, 도서, 가장).
    To reduce errors, we require the char BEFORE the particle to also be hangul,
    forming at least a 2-char word + particle + next word pattern.
    """
    if not text or len(text) < 3:
        return text

    result = list(text)
    insertions = set()

    for i in range(1, len(result) - 1):
        ch = result[i]  # potential particle
        if ch not in _PARTICLE_CHARS:
            continue
        prev = result[i - 1]
        nxt = result[i + 1]

        if not (_is_hangul(prev) and _is_hangul(nxt)):
            continue

        # Already has a space after
        if i + 1 < len(result) and result[i + 1] == ' ':
            continue

        has_prev_jong = _has_jong(prev)
        insert = False

        # Check 2-char and 3-char lookahead for exception words
        next2 = ch + nxt
        next3 = ''
        if i + 2 < len(result) and _is_hangul(result[i + 2]):
            next3 = ch + nxt + result[i + 2]

        if next3 in _EXCEPTIONS_3CHAR:
            continue

        # 받침O + 은/을/과
        if has_prev_jong and ch in ('은', '을', '과'):
            exceptions = _EXCEPTIONS_AFTER_JONG.get(ch, set())
            if next2 not in exceptions:
                insert = True

        # 받침X + 는/를/와
        elif not has_prev_jong and ch in ('는', '를', '와'):
            exceptions = _EXCEPTIONS_NO_JONG.get(ch, set())
            if next2 not in exceptions:
                insert = True

        # Any + 의/에/도 (but many exceptions)
        elif ch in ('의', '에', '도'):
            exceptions = _EXCEPTIONS_ANY.get(ch, set())
            # For these ambiguous particles, require the previous char to
            # have at least 1 more hangul before it (3+ char context)
            if i >= 2 and _is_hangul(result[i - 2]):
                if next2 not in exceptions:
                    insert = True

        if insert:
            insertions.add(i + 1)

    # Apply insertions in reverse order
    for pos in sorted(insertions, reverse=True):
        result.insert(pos, ' ')

    return ''.join(result)


def fix_korean_spacing(text):
    """
    Main entry point: fix Korean spacing issues from OCR output.

    Steps:
    1. Apply regex-based patterns (punctuation, numbers, multi-char particles, verb endings)
    2. Apply jamo-aware single-char particle detection
    3. Clean up double spaces
    """
    if not text:
        return text

    # Preserve paragraph breaks
    paragraphs = text.split('\n\n')
    fixed_paragraphs = []

    for para in paragraphs:
        # Step 1: regex-based patterns
        for pattern, replacement in _PATTERNS:
            para = pattern.sub(replacement, para)

        # Step 2: Single-char particle spacing (apply twice for cascading fixes)
        for _ in range(2):
            new_para = _insert_spaces_after_single_particles(para)
            if new_para == para:
                break
            para = new_para

        # Step 3: Clean up double spaces
        para = re.sub(r'  +', ' ', para)

        fixed_paragraphs.append(para)

    return '\n\n'.join(fixed_paragraphs)

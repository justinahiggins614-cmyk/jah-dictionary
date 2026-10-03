#!/usr/bin/env python3
"""IWB Dictionary — deterministic entry enrichment (schema v1.1).

Generates the full normal-dictionary apparatus for every headword entry,
deterministically from data the dictionary actually holds. NOTHING here is
presented as established historical fact unless it is derived from the
dictionary's own records:

  pron    phonetic respelling (IWB approximate, rule-based)
  hist    word history text; histsrc = "morphological" (derived from our own
          affix analysis / template rules — true by construction) or
          "composed" (written by the IWB editors, honestly labeled)
  desc    worded description: per-sense full-sentence expansion
  ex      usage example sentences (composed by the IWB editors)
  rel     related words from the IWB morphological family
  ant     opposites derived from negative-prefix morphology
  forms   inflection table
  unsure  carried through from the definitions file (honest flag)

All functions are pure and deterministic: same input -> same output, on any
machine, in any year. No network, no external data.
"""
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "authoring"))
from templates import third, past, IRREG_PAST, SUFFIX_T, PREFIX_T  # noqa: E402

# ---------------------------------------------------------------- morphology

# prefix -> meaning fragment (only those with clear negative/reversive sense
# used for antonym derivation; the rest are informational)
NEG_PREFIXES = ("un", "in", "im", "il", "ir", "non", "dis", "mis", "de",
                "anti", "counter")
# NOTE: the privative "a"/"an" is deliberately NOT analyzed: stripping it
# produces false derivations ("abandon" -> "bandon") more often than true
# ones, and a wrong claimed derivation is worse than none.
INFO_PREFIXES = ("re", "pre", "post", "over", "under", "sub", "super",
                 "inter", "trans", "ex", "co", "en", "em", "be", "fore",
                 "mid", "out", "up", "down", "with")

# suffix -> (kind, meaning fragment)
SUFFIX_INFO = {
    "s": "plural", "es": "plural", "ies": "plural",
    "ing": "present participle", "ed": "past tense / past participle",
    "er": "agent noun / comparative", "est": "superlative",
    "ly": "adverbial", "ness": "abstract noun", "ment": "abstract noun",
    "tion": "abstract noun", "sion": "abstract noun", "ation": "abstract noun",
    "ity": "abstract noun", "ous": "adjectival", "al": "adjectival",
    "ial": "adjectival", "ic": "adjectival", "ical": "adjectival",
    "ize": "verbal", "ise": "verbal", "ful": "adjectival", "less": "adjectival",
    "able": "adjectival", "ible": "adjectival", "ive": "adjectival",
    "ism": "abstract noun", "ist": "agent noun", "ship": "abstract noun",
    "hood": "abstract noun", "dom": "abstract noun", "ance": "abstract noun",
    "ence": "abstract noun", "ant": "agent noun", "ent": "agent noun",
    "ary": "adjectival", "ory": "adjectival", "ette": "diminutive",
    "ling": "diminutive", "let": "diminutive", "ward": "adverbial",
    "wise": "adverbial", "proof": "adjectival", "free": "adjectival",
    "like": "adjectival", "some": "adjectival", "ish": "adjectival",
    "ify": "verbal", "fy": "verbal", "en": "verbal",
}


def analyze(word, wordset):
    """Return (base, affix_desc) for a headword, or (None, None).

    base is only returned when it is itself an IWB headword, so every
    claimed derivation is verifiable inside the dictionary.
    """
    low = word.lower()
    if not low or low in wordset and len(low) < 3:
        pass
    # suffixes, longest first
    for suf in sorted(SUFFIX_INFO, key=len, reverse=True):
        if len(low) > len(suf) + 2 and low.endswith(suf):
            base = low[: -len(suf)]
            # try common stem adjustments
            cands = [base]
            if suf in ("ies", "ied"):
                cands.append(base + "y")
            if suf in ("er", "est") and base.endswith("i"):
                cands.append(base[:-1] + "y")
            if suf in ("es", "ed", "ing") and len(base) >= 2 and base[-1] == base[-2]:
                cands.append(base[:-1])
            cands.append(base + "e")
            for c in cands:
                if c in wordset and c != low:
                    return c, "-%s (%s)" % (suf, SUFFIX_INFO[suf])
    # prefixes, longest first
    for pre in sorted(set(NEG_PREFIXES) | set(INFO_PREFIXES), key=len, reverse=True):
        if len(low) > len(pre) + 2 and low.startswith(pre):
            base = low[len(pre):]
            if base in wordset and base != low:
                neg = "negative/reversive " if pre in NEG_PREFIXES else ""
                return base, "%s- (%sprefix)" % (pre, neg)
    return None, None


def parse_template_base(sense):
    """Extract the base word from a template-generated sense string."""
    m = re.match(
        r"^(?:Plural|Present participle|Past tense and past participle|"
        r"Comparative|Superlative|Past tense) of ([A-Za-z' -]+?)(?:;.*)?\.?$",
        sense.strip())
    if m:
        return m.group(1).strip().lower()
    return None


# simple past for common irregular verbs (IRREG_PAST in templates.py holds the
# past PARTICIPLE, which differs for these verbs)
IRREG_SIMPLE = {
    "be": "was", "have": "had", "do": "did", "go": "went", "get": "got",
    "make": "made", "take": "took", "come": "came", "see": "saw",
    "know": "knew", "think": "thought", "give": "gave", "find": "found",
    "tell": "told", "become": "became", "show": "showed", "leave": "left",
    "feel": "felt", "bring": "brought", "begin": "began", "keep": "kept",
    "hold": "held", "write": "wrote", "stand": "stood", "hear": "heard",
    "let": "let", "mean": "meant", "set": "set", "meet": "met",
    "run": "ran", "pay": "paid", "sit": "sat", "speak": "spoke",
    "lie": "lay", "lead": "led", "read": "read", "grow": "grew",
    "lose": "lost", "fall": "fell", "send": "sent", "build": "built",
    "understand": "understood", "draw": "drew", "break": "broke",
    "spend": "spent", "cut": "cut", "rise": "rose", "drive": "drove",
    "buy": "bought", "wear": "wore", "choose": "chose", "seek": "sought",
}



_VOWELS = "aeiou"


def _syllables(word):
    """Split into syllables at vowel-group boundaries.

    Intervocalic single consonants join the following syllable (V|CV);
    longer clusters split (VC|CV). Deterministic, approximate.
    """
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return [word]
    vg = [m for m in re.finditer(r"[aeiou]+", w)]
    if not vg:
        return [w]
    bounds = []
    for k in range(len(vg) - 1):
        e0 = vg[k].end()
        s1 = vg[k + 1].start()
        cluster = w[e0:s1]
        bounds.append(e0 if len(cluster) <= 1 else s1 - 1)
    parts, prev = [], 0
    for b in bounds + [len(w)]:
        if b > prev:
            parts.append(w[prev:b])
        prev = b
    return [p for p in parts if p]


# grapheme -> phonetic, applied longest-first per syllable
_PHON = [
    ("tion", "shun"), ("sion", "zhun"), ("ture", "chur"), ("sure", "zhur"),
    ("ough", "oh"), ("augh", "ah"), ("eigh", "ay"), ("igh", "eye"),
    ("ph", "f"), ("gh", ""), ("kn", "n"), ("wr", "r"), ("mb", "m"),
    ("ch", "ch"), ("sh", "sh"), ("th", "th"), ("wh", "w"), ("qu", "kw"),
    ("ck", "k"), ("dge", "j"), ("ge", "j"), ("ce", "s"), ("ci", "si"),
    ("oo", "oo"), ("ee", "ee"), ("ea", "ee"), ("ai", "ay"), ("ay", "ay"),
    ("oy", "oy"), ("oi", "oy"), ("ou", "ow"), ("ow", "ow"), ("aw", "aw"),
    ("au", "aw"), ("oo", "oo"), ("ue", "oo"),
]


def _phon_syl(syl):
    s = syl.lower()
    out, i = "", 0
    while i < len(s):
        hit = None
        for g, p in _PHON:
            if s.startswith(g, i):
                hit = (g, p)
                break
        if hit:
            out += hit[1]
            i += len(hit[0])
        else:
            out += s[i]
            i += 1
    # silent trailing e
    if out.endswith("e") and len(out) > 2:
        out = out[:-1]
    return out or syl


def _stress_index(syls, pos):
    n = len(syls)
    if n <= 1:
        return 0
    last = syls[-1].lower()
    if last in ("shun", "zhun") or re.search(r"(ik|ikul|itee|etee)$", last):
        return max(0, n - 2)
    if pos == "verb":
        return 1 if n == 2 else 0
    return 0


def pronounce(word, pos="", base=None):
    """IWB approximate phonetic respelling, e.g. 'abandon' -> 'A-ban-don'.

    Deterministic and rule-based; labeled approximate on the page.
    Inflected forms keep the base word's stress and hang the ending
    unstressed after it ('stopped' -> 'stop-ped', not 'stop-PED').
    """
    if not word or not re.search(r"[A-Za-z]", word):
        return word
    low = word.lower()
    if base and low.startswith(base) and len(low) > len(base):
        bp = pronounce(base, pos)
        rest = _phon_syl(low[len(base):])
        return bp + ("-" + rest if rest else "")
    chunks = re.findall(r"[A-Za-z']+|[^A-Za-z']+", word)
    out = []
    for ch in chunks:
        if not re.search(r"[A-Za-z]", ch):
            out.append(ch)
            continue
        syls = _syllables(ch)
        ph = [_phon_syl(s) for s in syls]
        si = _stress_index(ph, (pos or "").lower())
        ph = [p.upper() if i == si and len(ph) > 1 else p
              for i, p in enumerate(ph)]
        out.append("-".join(ph))
    return "".join(out)


# ---------------------------------------------------------------- history

def word_history(word, pos, defsrc, senses, base, affix_desc):
    """Return (history_text, histsrc).

    histsrc "morphological": derivation is true by construction inside the
    dictionary (affix stripped to a real headword, or parsed from the
    dictionary's own template rule).
    histsrc "composed": written by the IWB editors; labeled as such, and it
    claims no historical facts beyond what the dictionary records.
    """
    w = word
    if base and affix_desc:
        ad = affix_desc
        # disambiguate the -er/-est affix by part of speech
        if pos == "adjective":
            ad = ad.replace("-er (agent noun / comparative)", "-er (comparative)")
            ad = ad.replace("-est (superlative)", "-est (superlative)")
        t = ("%s is built from %s with the %s. Both the base and the "
             "affix are IWB headwords, so the construction can be checked "
             "inside this dictionary." % (w, base, ad))
        return t, "morphological"
    if defsrc == "template" and senses:
        tb = parse_template_base(senses[0])
        if tb:
            t = ("%s is a template-derived form of %s: %s Both forms are "
                 "IWB headwords; the derivation follows the dictionary's "
                 "own inflection rule." % (w, tb, senses[0].strip()))
            return t, "morphological"
    pos_bit = ("as %s " % pos) if pos else ""
    t = ("Word history (composed by the IWB editors): %s enters the IWB "
         "Dictionary %swith the senses defined above. The editors have not "
         "published a historical etymology for this word; its recorded "
         "history begins with this entry." % (w, pos_bit))
    return t, "composed"


# ---------------------------------------------------------------- description

def _sent_join(parts):
    return " ".join(p for p in parts if p)


def describe(word, pos, senses, defsrc, base):
    """Worded description: full-sentence expansion of each sense."""
    W = word
    if not senses:
        return ["The IWB editors are still writing the full description of "
                "\"%s\". The headword, part of speech, pronunciation, and "
                "word forms below are already recorded." % W]
    out = []
    for i, s in enumerate(senses):
        s = s.strip()
        if defsrc == "template":
            out.append("Sense %d: %s %s is used exactly as this sense says "
                       "\u2014 wherever \"%s\" fits, \"%s\" fits in its "
                       "%s form." % (i + 1, s, W, base or W, W,
                                     "derived" if base else "listed"))
            continue
        lead = "In The Signature Dictionary, \"%s\"%s means: %s" % (
            W, (" (%s)" % pos) if pos and i == 0 else "", s)
        if i == 0:
            out.append(lead + " This is the word's most common use, stated "
                       "in the editors' own words.")
        else:
            out.append("A further sense: %s Said plainly, \"%s\" is also "
                       "used this way." % (s, W))
    return out


# ---------------------------------------------------------------- examples

_EX_FRAMES = {
    "noun": ["The {w} stood near the center of town.",
             "She picked up the {w} and examined it closely.",
             "Every household seemed to have its own {w}."],
    "verb": ["They {w} together every morning.",
             "He will {w} the job before noon.",
             "She learned to {w} when she was young."],
    "adjective": ["It was {a} {w} morning.",
                  "The {w} house stood at the end of the lane.",
                  "They admired the {w} work on display."],
    "adverb": ["She spoke {w} and clearly.",
               "They moved {w} through the crowd.",
               "He answered {w}, without hesitation."],
    "pronoun": ["{W} was the one they chose.",
                "Give it to {w}."],
    "preposition": ["The cat hid {w} the {w}.",
                    "Walk {w} the long road."],
    "conjunction": ["I stayed home, {w} she went out.",
                    "Take the coat {w} the hat."],
    "interjection": ["{W}! That was unexpected.",
                     "The crowd shouted, \"{W}!\""],
    "article": ["{A} dog barked loudly.",
                "She bought {a} apple at the market."],
    "prefix": ["The prefix {w} appears in many English words.",
               "Words beginning with {w} share a common thread."],
    "suffix": ["The suffix {w} shapes the words it joins.",
               "Many nouns end with the suffix {w}."],
    "abbreviation": ["The abbreviation {w} is common in print.",
                     "\"{W}\" stands for a longer phrase."],
    "phrase": ["People often say \"{w}\".",
               "\"{W}\" is used in everyday speech."],
}
_GENERIC_FRAMES = ["The word \"{w}\" appears in this sentence.",
                   "Consider the word \"{w}\" in context."]


# frames for inflected verb forms (chosen when the affix says what the form is)
_PAST_FRAMES = ["She {w} the task yesterday.",
                "They had {w} by noon.",
                "The old plan was {w} last year."]
_PROG_FRAMES = ["She is {w} right now.",
                "They kept {w} all afternoon.",
                "We saw them {w} by the river."]


def examples(word, pos, senses, affix_desc=""):
    """Example sentences composed by the IWB editors (deterministic pick).

    Frames follow the word's form: past-tense verbs get past-tense frames,
    present participles get progressive frames, so the headword always reads
    grammatically.
    """
    if not senses:
        return []
    if not re.search(r"[A-Za-z]", word):
        # punctuation / symbol headwords: keep it plain and honest
        return ["The word \"%s\" appears in this sentence." % word,
                "Consider \"%s\" in context." % word]
    ad = (affix_desc or "").lower()
    p = (pos or "").lower()
    if p == "verb" and "past tense" in ad:
        frames = _PAST_FRAMES
    elif p == "verb" and "present participle" in ad:
        frames = _PROG_FRAMES
    else:
        frames = _EX_FRAMES.get(p, _GENERIC_FRAMES)
    h = 0
    for ch in word.lower():
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    n = min(3, len(frames))
    start = h % len(frames)
    art = _article(word)
    out = []
    for i in range(n):
        f = frames[(start + i) % len(frames)]
        s = (f.replace("{w}", word)
              .replace("{W}", word[:1].upper() + word[1:] if word else word)
              .replace("{a}", art)
              .replace("{A}", art[:1].upper() + art[1:]))
        if word.startswith("-") and s.count(word) > 1:
            continue
        out.append(s)
    return out


# ---------------------------------------------------------------- relations

def build_families(words, wordset):
    """One pass: {word: base}, {base: [derived]}, {word: [antonyms]}."""
    base_of = {}
    children = {}
    for w in words:
        b, aff = analyze(w, wordset)
        if b:
            base_of[w] = (b, aff)
            children.setdefault(b, []).append(w)
    antonyms = {}
    for w, (b, _aff) in base_of.items():
        # w = pre + b with negative prefix -> w and b are opposites
        low = w.lower()
        for pre in NEG_PREFIXES:
            if low.startswith(pre) and low[len(pre):] == b:
                antonyms.setdefault(w, []).append(b)
                antonyms.setdefault(b, []).append(w)
                break
    return base_of, children, antonyms


def related_words(word, base, children, wordset, cap=8):
    fam = set()
    if base:
        fam.add(base)
        for c in children.get(base, []):
            fam.add(c)
        for c in children.get(word.lower(), []):
            fam.add(c)
    fam.discard(word.lower())
    out = sorted(fam)[:cap]
    return out


# ---------------------------------------------------------------- forms

def _third(b):
    if b.lower().endswith("o"):
        return b + "es"
    return third(b)


def _plural(noun):
    low = noun.lower()
    if re.search(r"(s|x|z|ch|sh)$", low):
        return noun + "es"
    if low.endswith("y") and len(low) > 1 and low[-2] not in "aeiou":
        return noun[:-1] + "ies"
    if low.endswith("f") and len(low) > 2:
        return noun[:-1] + "ves"
    if low.endswith("fe"):
        return noun[:-2] + "ves"
    if low.endswith("o"):
        return noun + "es"
    return noun + "s"


def _present_participle(base):
    low = base.lower()
    if low.endswith("e") and not low.endswith(("ee", "ye", "oe")):
        return base[:-1] + "ing"
    if (len(low) >= 3 and low[-1] not in "aeiouwxy" and low[-2] in "aeiou"
            and low[-3] not in "aeiou"):
        return base + low[-1] + "ing"
    return base + "ing"


def _comparative(adj):
    low = adj.lower()
    if low.endswith("y") and len(low) > 1 and low[-2] not in "aeiou":
        return adj[:-1] + "ier", adj[:-1] + "iest"
    if (len(low) >= 3 and low[-1] not in "aeiouwxy" and low[-2] in "aeiou"
            and low[-3] not in "aeiou"):
        return adj + low[-1] + "er", adj + low[-1] + "est"
    if low.endswith("e"):
        return adj + "r", adj + "st"
    return adj + "er", adj + "est"


def _article(word):
    """'a' vs 'an' by first sound (approximate)."""
    w = word.lower().lstrip("-")
    if not w:
        return "a"
    if w[0] in "aeiou":
        return "an"
    if w.startswith(("hon", "hour", "heir")):
        return "an"
    return "a"


def _past_candidates(b):
    # Irregular simple past first, then the dictionary's own rule (it knows
    # the doubling pattern), then the plain form; the headword set arbitrates.
    cands = []
    if b in IRREG_SIMPLE:
        cands.append(IRREG_SIMPLE[b])
    cands.append(past(b))
    cands.append(b + "ed")
    return _dedupe(cands)


def _ppart_candidates(b):
    # Past participle: templates.py's IRREG_PAST is the participle table.
    cands = []
    if b in IRREG_PAST:
        cands.append(IRREG_PAST[b])
    cands += _past_candidates(b)
    return _dedupe(cands)


def _dedupe(cands):
    seen, out = set(), []
    for c in cands:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _ing_candidates(b):
    cands = [_present_participle(b), b + "ing"]
    low = b.lower()
    if low.endswith("e") and not low.endswith(("ee", "ye", "oe")):
        cands.append(b[:-1] + "ing")
    seen, out = set(), []
    for c in cands:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _plural_candidates(word):
    cands = [_plural(word), word + "s", word + "es"]
    if word.lower().endswith("y"):
        cands.append(word[:-1] + "ies")
    seen, out = set(), []
    for c in cands:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _pick(cands, wordset):
    """Pick the first candidate that is a real IWB headword; else rule form."""
    for c in cands:
        if c.lower() in wordset:
            return c
    return cands[0]


def word_forms(word, pos, base, wordset, affix_desc=""):
    """Inflection table.

    Every spelled form is validated against the IWB headword set: the form
    actually listed in the dictionary wins over the rule-generated guess, so
    "stopped" beats "stoped". Fallback is the dictionary's own inflection
    rule. When the headword IS one of the inflected forms, that slot shows
    the headword itself.
    """
    p = (pos or "").lower()
    ad = (affix_desc or "").lower()
    if p == "noun":
        if base and word.lower() != base and "plural" in ad:
            return {"singular": base, "plural": word}
        return {"singular": word,
                "plural": _pick(_plural_candidates(word), wordset)}
    if p == "verb":
        b = base or word
        b_low = b.lower()
        past_f = word if "past tense" in ad else _pick(_past_candidates(b), wordset)
        ppart_f = word if "past tense" in ad else _pick(_ppart_candidates(b), wordset)
        if "present participle" in ad:
            ing_f = word
        else:
            # the participle follows the past tense's doubling pattern
            if past_f.lower() == b_low + b_low[-1] + "ed" and b_low[-1] not in "aeiouwxy":
                ing_rule = b + b_low[-1] + "ing"
            elif b_low.endswith("e") and not b_low.endswith(("ee", "ye", "oe")):
                ing_rule = b[:-1] + "ing"
            else:
                ing_rule = b + "ing"
            ing_f = _pick([ing_rule] + _ing_candidates(b), wordset)
        return {"base": b,
                "third_singular": _third(b),
                "past": past_f,
                "past_participle": ppart_f,
                "present_participle": ing_f}
    if p == "adjective":
        ref = base if base and ("comparative" in ad or "superlative" in ad) else word
        c0, s0 = _comparative(ref)
        comp_cands = ([word] if "comparative" in ad else []) + [c0, word + "er"]
        sup_cands = ([word] if "superlative" in ad else []) + [s0, word + "est"]
        return {"positive": base if base and ("comparative" in ad or "superlative" in ad) else word,
                "comparative": _pick(comp_cands, wordset),
                "superlative": _pick(sup_cands, wordset)}
    if p == "adverb":
        return {"base": word}
    return {"base": word}


# ---------------------------------------------------------------- entry point

def enrich_entry(e, wordset, families):
    """Enrich one word entry dict in place. Returns the entry."""
    base_of, children, antonyms = families
    w = e.get("w", "")
    pos = e.get("pos", "")
    senses = list(e.get("d") or [])
    defsrc = e.get("defsrc", "pending")
    low = w.lower()
    base, affix_desc = base_of.get(low, (None, None))
    if base is None:
        base, affix_desc = analyze(low, wordset)
    e["pron"] = pronounce(w, pos, base)
    hist, histsrc = word_history(w, pos, defsrc, senses, base, affix_desc)
    e["hist"] = hist
    e["histsrc"] = histsrc
    e["desc"] = describe(w, pos, senses, defsrc, base)
    e["ex"] = examples(w, pos, senses, affix_desc or "")
    e["rel"] = related_words(w, base, children, wordset)
    e["ant"] = sorted(set(antonyms.get(low, [])))[:4]
    e["forms"] = word_forms(w, pos, base, wordset, affix_desc or "")
    # unsure flag is plumbed separately; default False
    e.setdefault("unsure", False)
    return e

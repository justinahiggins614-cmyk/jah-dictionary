#!/usr/bin/env python3
"""IWB Dictionary — original definition templates for derived/inflected words.
Every definition below is written fresh for the IWB Dictionary (not Webster's).
Outputs data/definitions/templates.jsonl : {"w","pos","d":[senses],"src":"template","rule":...}
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
DICT_JSON = os.path.join(HERE, '..', 'build', 'dictionary.json')
OUT = os.path.join(HERE, '..', '..', '..', 'data', 'definitions', 'templates.jsonl')

IRREG_PAST = {'read':'read','write':'written','go':'gone','be':'been','have':'had','do':'done',
 'make':'made','take':'taken','come':'come','see':'seen','get':'gotten','give':'given',
 'run':'run','eat':'eaten','drink':'drunk','swim':'swum','sing':'sung','ring':'rung',
 'speak':'spoken','break':'broken','choose':'chosen','drive':'driven','ride':'ridden',
 'rise':'risen','wake':'woken','steal':'stolen','tear':'torn','wear':'worn','bear':'born',
 'swear':'sworn','forget':'forgotten','forgive':'forgiven','freeze':'frozen','hide':'hidden',
 'bite':'bitten','fall':'fallen','shake':'shaken','throw':'thrown','grow':'grown','know':'known',
 'fly':'flown','draw':'drawn','lie':'lain','lay':'laid','pay':'paid','say':'said','sell':'sold',
 'tell':'told','send':'sent','spend':'spent','build':'built','lose':'lost','shoot':'shot',
 'sit':'sat','stand':'stood','understand':'understood','win':'won','begin':'begun','cut':'cut',
 'put':'put','set':'set','shut':'shut','quit':'quit','hurt':'hurt','cost':'cost','hit':'hit'}

def third(base):
    if base.endswith(('s','x','z','ch','sh')): return base+'es'
    if base.endswith('y') and len(base)>1 and base[-2] not in 'aeiou': return base[:-1]+'ies'
    return base+'s'

def past(base):
    if base in IRREG_PAST: return IRREG_PAST[base]
    if base.endswith('e'): return base+'d'
    if base.endswith('y') and len(base)>1 and base[-2] not in 'aeiou': return base[:-1]+'ied'
    if len(base)>=3 and base[-1] not in 'aeiouwy' and base[-2] in 'aeiou' and base[-3] not in 'aeiou':
        return base+base[-1]+'ed'
    return base+'ed'

# (analysis-kind, suffix/prefix) -> (pos, template fn)
def T(kind):
    return kind

SUFFIX_T = {
 's':   ('noun',  lambda b: f"Plural of {b}."),
 'es':  ('noun',  lambda b: f"Plural of {b}."),
 'ies': ('noun',  lambda b: f"Plural of {b}."),
 'ing': ('verb',  lambda b: f"Present participle of {b}."),
 'ed':  ('verb',  lambda b: f"Past tense and past participle of {b}."),
 'er_cmp': ('adjective', lambda b: f"Comparative of {b}; more {b}."),
 'est': ('adjective', lambda b: f"Superlative of {b}; most {b}."),
 'er_agt': ('noun', lambda b: f"One who {third(b)}."),
 'ly':  ('adverb', lambda b: f"In a {b} manner."),
 'ness':('noun',  lambda b: f"The quality or state of being {b}."),
 'ment':('noun',  lambda b: f"The act or result of {b}."),
 'tion':('noun',  lambda b: f"The act or process of {b}."),
 'sion':('noun',  lambda b: f"The act or process of {b}."),
 'ation':('noun', lambda b: f"The act or process of {b}."),
 'ity': ('noun',  lambda b: f"The quality or state of being {b}."),
 'ous': ('adjective', lambda b: f"Full of {b}; having the nature of {b}."),
 'al':  ('adjective', lambda b: f"Relating to {b}."),
 'ial': ('adjective', lambda b: f"Relating to {b}."),
 'ic':  ('adjective', lambda b: f"Relating to {b}; characteristic of {b}."),
 'ical':('adjective', lambda b: f"Relating to {b}; characteristic of {b}."),
 'ize': ('verb',  lambda b: f"To make {b}; to become {b}."),
 'ise': ('verb',  lambda b: f"To make {b}; to become {b}."),
 'ful': ('adjective', lambda b: f"Full of {b}."),
 'less':('adjective', lambda b: f"Without {b}; lacking {b}."),
 'able':('adjective', lambda b: f"That can be {past(b)}."),
 'ible':('adjective', lambda b: f"That can be {past(b)}."),
 'ive': ('adjective', lambda b: f"Tending to {b}."),
 'ism': ('noun',  lambda b: f"The system, doctrine, or practice of {b}."),
 'ist': ('noun',  lambda b: f"One who practices or supports {b}."),
 'ship':('noun',  lambda b: f"The state or office of being {b}."),
 'hood':('noun',  lambda b: f"The state of being {b}."),
 'dom': ('noun',  lambda b: f"The domain or state of {b}."),
 'ance':('noun',  lambda b: f"The act or state of {b}."),
 'ence':('noun',  lambda b: f"The act or state of {b}."),
 'ant': ('noun',  lambda b: f"One that {third(b)}."),
 'ent': ('noun',  lambda b: f"One that {third(b)}."),
 'ary': ('adjective', lambda b: f"Having to do with {b}."),
 'ory': ('adjective', lambda b: f"Having to do with {b}."),
 'ette':('noun',  lambda b: f"A small {b}."),
 'ling':('noun',  lambda b: f"A small or young {b}."),
 'let': ('noun',  lambda b: f"A small {b}."),
 'ward':('adverb', lambda b: f"In the direction of {b}."),
 'wise':('adverb', lambda b: f"In the manner of {b}."),
 'proof':('adjective', lambda b: f"Resistant to {b}."),
 'free':('adjective', lambda b: f"Without {b}; free from {b}."),
 'like':('adjective', lambda b: f"Resembling {b}."),
 'some':('adjective', lambda b: f"Characterized by {b}."),
 'ish': ('adjective', lambda b: f"Somewhat {b}; like {b}."),
 'ify': ('verb',  lambda b: f"To make {b}."),
 'fy':  ('verb',  lambda b: f"To make {b}."),
 'en':  ('verb',  lambda b: f"To make {b}; to become {b}."),
}
PREFIX_T = {
 'un': ('', lambda b: f"Not {b}."),
 'in': ('', lambda b: f"Not {b}."),
 'im': ('', lambda b: f"Not {b}."),
 'il': ('', lambda b: f"Not {b}."),
 'ir': ('', lambda b: f"Not {b}."),
 'non': ('', lambda b: f"Not {b}."),
 'dis': ('', lambda b: f"Not {b}; the opposite of {b}."),
 're': ('verb', lambda b: f"To {b} again."),
 'pre': ('', lambda b: f"Before {b}."),
 'post': ('', lambda b: f"After {b}."),
 'sub': ('', lambda b: f"Under {b}; a division of {b}."),
 'super': ('', lambda b: f"Above {b}; beyond {b}."),
 'over': ('', lambda b: f"Too much {b}; above {b}."),
 'under': ('', lambda b: f"Below {b}."),
 'mis': ('verb', lambda b: f"To {b} badly or wrongly."),
 'de': ('verb', lambda b: f"To remove {b}; to reverse {b}."),
 'ex': ('', lambda b: f"Former {b}."),
 'co': ('', lambda b: f"Together with {b}; joint {b}."),
 'anti': ('', lambda b: f"Against {b}; opposed to {b}."),
 'counter': ('', lambda b: f"Against {b}; in opposition to {b}."),
 'bi': ('', lambda b: f"Having two {b}."),
 'tri': ('', lambda b: f"Having three {b}."),
 'semi': ('', lambda b: f"Half {b}; partly {b}."),
 'multi': ('', lambda b: f"Many {b}."),
 'poly': ('', lambda b: f"Many {b}."),
 'micro': ('', lambda b: f"Very small {b}."),
 'macro': ('', lambda b: f"Large-scale {b}."),
 'auto': ('', lambda b: f"Self {b}; automatic {b}."),
 'hyper': ('', lambda b: f"Excessively {b}."),
 'hypo': ('', lambda b: f"Under {b}; less than normal."),
 'extra': ('', lambda b: f"Beyond {b}."),
 'ultra': ('', lambda b: f"Extremely {b}."),
 'fore': ('', lambda b: f"Before {b}."),
 'out': ('', lambda b: f"Beyond {b}."),
 'with': ('', lambda b: f"Against {b}."),
 'self': ('', lambda b: f"Of oneself; automatic {b}."),
}

def main():
    d = json.load(open(DICT_JSON))
    words = sorted(d.keys())
    wordset = set(w.lower() for w in words)
    out = open(OUT, 'w')
    n = 0
    for w in words:
        wl = w.lower()
        done = False
        # compounds
        for i in range(3, len(wl)-2):
            a, b = wl[:i], wl[i:]
            if a in wordset and b in wordset:
                rec = {"w": w, "pos": "", "d": [f"A {b} connected with {a}."], "src": "template", "rule": f"compound:{a}+{b}"}
                out.write(json.dumps(rec)+"\n"); n+=1; done=True; break
        if done: continue
        # prefixes
        for p in sorted(PREFIX_T, key=len, reverse=True):
            if wl.startswith(p) and len(wl)>len(p)+2 and wl[len(p):] in wordset:
                pos, fn = PREFIX_T[p]
                rec = {"w": w, "pos": pos, "d": [fn(wl[len(p):])], "src": "template", "rule": f"prefix:{p}"}
                out.write(json.dumps(rec)+"\n"); n+=1; done=True; break
        if done: continue
        # suffixes (reuse analyzer order)
        cands = []
        if wl.endswith('ies') and len(wl)>4 and wl[:-3]+'y' in wordset: cands.append((wl[:-3]+'y','ies'))
        if wl.endswith('es') and len(wl)>3 and wl[:-2] in wordset: cands.append((wl[:-2],'es'))
        if wl.endswith('s') and len(wl)>3 and not wl.endswith('ss') and wl[:-1] in wordset: cands.append((wl[:-1],'s'))
        if wl.endswith('ing') and len(wl)>5:
            b=wl[:-3]
            if b in wordset: cands.append((b,'ing'))
            elif b+'e' in wordset: cands.append((b+'e','ing'))
            elif len(b)>=2 and b[-1]==b[-2] and b[:-1] in wordset: cands.append((b[:-1],'ing'))
        if wl.endswith('ied') and len(wl)>4 and wl[:-3]+'y' in wordset: cands.append((wl[:-3]+'y','ed'))
        elif wl.endswith('ed') and len(wl)>4:
            b=wl[:-2]
            if b in wordset: cands.append((b,'ed'))
            elif b+'e' in wordset: cands.append((b+'e','ed'))
            elif wl[:-1] in wordset: cands.append((wl[:-1],'ed'))
            elif len(b)>=2 and b[-1]==b[-2] and b[:-1] in wordset: cands.append((b[:-1],'ed'))
        if wl.endswith('est') and len(wl)>5 and wl[:-3] in wordset: cands.append((wl[:-3],'est'))
        if wl.endswith('ier') and len(wl)>4 and wl[:-3]+'y' in wordset: cands.append((wl[:-3]+'y','er_cmp'))
        elif wl.endswith('er') and len(wl)>4:
            b=wl[:-2]
            # comparative if -est form exists
            is_cmp = (b+'est' in wordset) or (b+'est' in wordset)
            if b in wordset: cands.append((b,'er_cmp' if is_cmp else 'er_agt'))
            elif b+'e' in wordset:
                bb=b+'e'; is_cmp2=(bb+'est' in wordset)
                cands.append((bb,'er_cmp' if is_cmp2 else 'er_agt'))
            elif len(b)>=2 and b[-1]==b[-2] and b[:-1] in wordset:
                bb=b[:-1]; is_cmp3=(bb+'est' in wordset)
                cands.append((bb,'er_cmp' if is_cmp3 else 'er_agt'))
        for suf in ['ation','tion','sion','ness','less','ment','able','ible','ship','hood','ence','ance','ical','ful','ity','ous','ize','ise','ist','ism','ive','ial','ary','ory','ette','ling','let','ward','wise','proof','free','like','some','ish','ify','ly','al','ic','en','ant','ent']:
            if wl.endswith(suf) and len(wl)>len(suf)+2:
                b=wl[:-len(suf)]
                if b in wordset: cands.append((b,suf)); break
                if suf in ('ation','tion','sion','ity','ous','al','ic') and b.endswith('i') and b[:-1]+'y' in wordset:
                    cands.append((b[:-1]+'y',suf)); break
                if suf=='able' and b+'e' in wordset: cands.append((b+'e',suf)); break
        if cands:
            base, suf = cands[0]
            if suf in SUFFIX_T:
                pos, fn = SUFFIX_T[suf]
                rec = {"w": w, "pos": pos, "d": [fn(base)], "src": "template", "rule": f"suffix:{suf}:{base}"}
                out.write(json.dumps(rec)+"\n"); n+=1
    out.close()
    print("template definitions:", n)
main()

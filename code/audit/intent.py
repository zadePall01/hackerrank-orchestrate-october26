"""Bounded multilingual intent classification; unknown phrasing is an error."""
import re
import unicodedata
from .contracts import AuditError


def authorizes_deletion(text: str) -> bool:
    raw = unicodedata.normalize('NFKC', text.casefold().replace('’', "'"))
    # Fold Latin accents only. Removing every combining mark also removes
    # Japanese voicing marks and can change negation text before matching.
    def latin_fold(value: str) -> str:
        return ''.join(''.join(c for c in unicodedata.normalize('NFKD',char) if not unicodedata.combining(c)) if 'LATIN' in unicodedata.name(char,'') else char for char in value)
    # A quoted command or procedural question is not the subject's consent.
    raw = re.sub(r'"[^"\n]*"|`[^`\n]*`|「[^」]*」|『[^』]*』', ' ', raw)
    value=latin_fold(raw)
    if re.match(r'\s*(?:how (?:do|can|would) i|what (?:happens|would happen) if|if i|tell me about (?:your |the )?(?:deletion|privacy))\b', value):
        return False
    negative = [r"(?:do not|don't|not a request to|without)\s+(?:delete|erase|remov)", r'leave .{0,80} in place', r'continue using', r'keep .{0,50} account', r'not .{0,15} delet', r'only .{0,35}(?:unsubscribe|marketing|correct|download)']
    negative += [r'\bnao\s+(?:solicito|quero|autorizo)\s+(?:(?:a|uma)\s+)?(?:exclusao|eliminacao|remocao)',r'\bnao\s+(?:exclu\w*|elimin\w*|apag\w*|remov\w*)',r'\bno\s+(?:elimin\w*|borr\w*|suprim\w*)',r'\bno\s+(?:quiero|solicito|autorizo)\s+(?:(?:la|una)\s+)?(?:eliminacion|supresion)',r'\bne\s+.{0,30}(?:supprim\w*|effac\w*).{0,10}pas',r'\bne\s+(?:demande|souhaite|veux).{0,10}pas.{0,20}(?:suppression|effacement)',r'削除(?:しないで|しない|を希望しません|を依頼しません)',r'삭제(?:하지\s*(?:마|않|말)|를\s*(?:원하지|요청하지))']
    deletion = [r'\bdelet\w*', r'\berase\w*', r'\bremov\w* .{0,70}(?:account|profile|personal|records|search|identifiers|name|contact)', r'\bclos\w* .{0,35}account', r'suppression', r'eliminacion', r'eliminar', r'exclusao', '削除', '삭제', r'(?:account|profile).{0,70}(?:already been removed|is gone).{0,80}(?:confirm|remaining)', r'(?:account|profile).{0,80}already been removed']
    deletion += [r'\b(?:exclu\w*|apag\w*)\b.{0,60}\bconta\b',r'\b(?:elimin\w*|borr\w*)\b.{0,60}\bcuenta\b',r'\b(?:supprim\w*|effac\w*)\b.{0,60}\bcompte\b']
    clauses = re.split(r'[.!?;。！？；、]|\b(?:but|however|mas|pero|mais)\b|ただし|しかし|하지만|그러나',value)
    negated = False
    for clause in clauses:
        if any(re.search(p,clause) for p in negative):
            negated = True
            continue
        if any(re.search(p,clause) for p in deletion): return True
    if negated: return False
    nondeletion = [r'copy', r'portable', r'export', r'information request', r'unsubscribe', r'marketing', r'correct', r'misspelled', r'change .{0,40}(?:email|number)', r'number .{0,40} out of date', r'access']
    if any(re.search(p, value) for p in nondeletion):
        return False
    raise AuditError('Unrecognized request intent; no deletion authorization inferred')

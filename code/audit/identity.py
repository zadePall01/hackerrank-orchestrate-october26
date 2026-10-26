"""Exact identifier indexing without name-based merges or email-provider guesses."""
from __future__ import annotations
from collections import defaultdict
import re
import unicodedata
from .contracts import AuditError, timestamp


def normalize(value: str) -> str:
    return unicodedata.normalize('NFKC', str(value)).strip().casefold()


def strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield normalize(value)


IDENTITY_FIELDS = {'user_id','email','phone','email_hash','customer_reference','subject_reference','subject_ref','subject_selector','lookup_key','lookup_value','correlation_key','query','subject_key','match_key','matched_value','matched_identifier','requester_email','requester_phone','owner_email','owner_phone','owner_key','customer_email','uploaded_by','message_text','message_excerpt','details','document','profile'}


def identity_strings(attributes: dict):
    """Only semantic identity-bearing fields may establish resource ownership."""
    for key,value in attributes.items():
        if key in IDENTITY_FIELDS:
            if isinstance(value,dict): yield from identity_strings(value)
            else: yield from strings(value)


class Identities:
    def __init__(self, current: list[dict], history: list[dict]):
        self.current = {r['user_id']: r for r in current}
        self.history = history
        self.index: dict[str, set[str]] = defaultdict(set)
        for row in current:
            for key in ('user_id', 'email', 'phone', 'email_hash'):
                if row[key]: self.index[normalize(row[key])].add(row['user_id'])
        for row in history:
            if row['field_name'] in {'email', 'phone', 'email_hash'}:
                for key in ('old_value', 'new_value'):
                    if row[key]: self.index[normalize(row[key])].add(row['user_id'])

    def resolve(self, email: str) -> str:
        matches = self.index.get(normalize(email), set())
        if len(matches) != 1:
            raise AuditError(f'Identity resolution has {len(matches)} candidates')
        return next(iter(matches))

    def aliases(self, user: str, cutoff: str) -> set[str]:
        # Current values are retrieval keys, not observations of historical resource state.
        row = self.current[user]
        result = {normalize(row[k]) for k in ('user_id', 'email', 'phone', 'email_hash') if row[k]}
        for event in self.history:
            if event['user_id'] == user and timestamp(event['event_time']) <= timestamp(cutoff) and event['field_name'] in {'email', 'phone', 'email_hash'}:
                result.update(normalize(event[k]) for k in ('old_value', 'new_value') if event[k])
        return result


def matches(attributes: dict, aliases: set[str]) -> bool:
    for text in identity_strings(attributes):
        if text in aliases:
            return True
        # Identifiers in free-form message text require token boundaries.
        for alias in aliases:
            if alias and re.search(r'(?<![\w@.+-])' + re.escape(alias) + r'(?![\w@.+-])', text):
                return True
    return False

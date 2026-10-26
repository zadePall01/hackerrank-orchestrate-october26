"""Grounded resource discovery and cutoff-aware state reconstruction."""
from __future__ import annotations
from collections import defaultdict
import re
from .contracts import AuditError, Observation, timestamp
from .extract import Extractor, SYSTEM_CATEGORY
from .identity import Identities, identity_strings, normalize, matches
from .policy import Policy
from .security import identifier


class StateIndex:
    def __init__(self, extracted: Extractor, identities: Identities, activity: list[dict], policy: Policy | None = None):
        self.extracted, self.identities, self.activity = extracted, identities, activity
        self.policy = policy
        self.resources: dict[tuple[str, str], list[Observation]] = defaultdict(list)
        self.identifiers: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for obs in extracted.observations:
            key = obs.system, obs.resource
            self.resources[key].append(obs)
            for value in identity_strings(obs.attributes):
                self.identifiers[value].add(key)
                for token in re.findall(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\buser_\d+\b|\b[a-f0-9]{64}\b', value):
                    self.identifiers[normalize(token)].add(key)

    def _discover(self, request: dict) -> tuple[str, set[tuple[str, str]], dict]:
        user = self.identities.resolve(request['email'])
        aliases = self.identities.aliases(user, request['audit_at']) | {normalize(request['email'])}
        keys = set()
        links: dict[tuple[str,str],tuple[str,str]] = {}
        for alias in aliases:
            for key in self.identifiers.get(alias, set()):
                if any(o.eligible(request['audit_at']) and matches(o.attributes, aliases) for o in self.resources[key]): keys.add(key)
        # Catalog links establish identity, never resource state.
        for event in self.activity:
            if event['event_type'] == 'LINK_RESOURCE_IDENTITY' and timestamp(event['event_time']) <= timestamp(request['audit_at']) and matches({'details': event['details']}, aliases):
                key=(event['target_system'],event['resource_id'])
                keys.add(key);links[key]=(event['event_time'],event['activity_id'])
        # Explicit stored resource relationships are identity evidence, never
        # evidence that a deletion operation succeeded. Cycles terminate via
        # visited keys; ambiguous service routing is not guessed from ID suffixes.
        pending=list(sorted(keys));visited=set()
        while pending:
            key=pending.pop()
            if key in visited:continue
            visited.add(key)
            if len(visited)>1000:raise AuditError('Resource relationship traversal exceeds budget')
            for parent in self.resources.get(key,[]):
                if not parent.eligible(request['audit_at']):continue
                source=parent.attributes.get('source_resource_id')
                if not source:continue
                identifier(source)
                events=[e for e in self.activity if e['resource_id']==source and e['target_system'] in SYSTEM_CATEGORY and timestamp(e['event_time'])<=timestamp(request['audit_at'])]
                systems={e['target_system'] for e in events}
                if len(systems)!=1:continue
                system=next(iter(systems));target=(system,source)
                available=max(timestamp(parent.captured_at),timestamp(parent.observed_at),min(timestamp(e['event_time']) for e in events)).isoformat()
                if key in links:available=max(timestamp(available),timestamp(links[key][0])).isoformat()
                proof=(available,parent.evidence_id)
                if target not in links or timestamp(available)<timestamp(links[target][0]):links[target]=proof
                if target not in keys:keys.add(target);pending.append(target)
        return user, keys, links

    def discover(self, request: dict) -> tuple[str, set[tuple[str,str]]]:
        user,keys,_=self._discover(request)
        return user,keys

    def resolve(self, request: dict) -> list[Observation]:
        user, keys, links = self._discover(request)
        aliases = self.identities.aliases(user, request['audit_at']) | {normalize(request['email'])}
        subject_files = {o.evidence_id for key in keys for o in self.resources.get(key, []) if o.eligible(request['audit_at']) and matches(o.attributes, aliases)}
        if not keys: raise AuditError('No subject-linked resource observations at cutoff')
        results = []
        for key in sorted(keys):
            observations = [o for o in self.resources.get(key, []) if o.eligible(request['audit_at'])]
            # Collection snapshots may prove an already identified resource absent.
            categories = {o.category for o in observations}
            if not categories and key in links and key[0] in SYSTEM_CATEGORY:categories.add(SYSTEM_CATEGORY[key[0]])
            for scope in self.extracted.scopes:
                if scope.complete and scope.category in {'USER_PROFILE', 'SEARCH_INDEX_ENTRY', 'SECONDARY_IDENTIFIER', 'CACHE_ENTRY', 'SUPPORT_ATTACHMENT', 'USER_EXPORT', 'MARKETING_PROFILE'} and (scope.evidence_id in subject_files or key in links) and scope.system == key[0] and scope.category in categories and key[1] not in scope.resources:
                    available=scope.captured_at
                    attributes={}
                    if key in links:
                        available=max(timestamp(available),timestamp(links[key][0])).isoformat()
                        attributes={'identity_link_evidence_id':links[key][1],'identity_link_available_at':links[key][0]}
                    candidate = Observation(scope.evidence_id, available, scope.observed_at, key[0], key[1], scope.category, 'ABSENT', attributes, f'complete collection {scope.name}', scope.name)
                    if candidate.eligible(request['audit_at']): observations.append(candidate)
            if not observations:
                raise AuditError(f'Identity link without observed resource state: {key[0]}/{key[1]}')
            # A newer primary read says nothing about an independently captured
            # replica. Advance each store's timeline independently, then require
            # every store to comply before choosing a compliant verification.
            stores: dict[str, list[Observation]] = defaultdict(list)
            for obs in observations:
                physical = obs.scope.rsplit(':', 1)[-1] if 'replica' in obs.scope else 'primary'
                stores[physical].append(obs)
            current = []
            for store in stores.values():
                latest_time = max(timestamp(o.observed_at) for o in store)
                latest = [o for o in store if timestamp(o.observed_at) == latest_time]
                if len({o.state for o in latest}) > 1:
                    raise AuditError(f'Conflicting simultaneous observations: {key[0]}/{key[1]}')
                current.append(min(latest, key=lambda o: (o.captured_at,o.evidence_id,o.locator)))
            def violation(obs: Observation) -> bool:
                if self.policy is not None:
                    return self.policy.assess(obs,request['audit_at'])[2] is not None
                # Unit-level state-only callers have no policy interpreter.
                return obs.state in {'PRESENT','ACTIVE'} and obs.category not in {'SECURITY_AUDIT_LOG','LEGAL_HOLD_RECORD'}
            risks = [o for o in current if violation(o)]
            selected = min(risks or current, key=lambda o: (-timestamp(o.observed_at).timestamp(), o.captured_at, o.evidence_id, o.locator))
            results.append(selected)
        return results

    @staticmethod
    def has_account_coverage(observations: list[Observation]) -> bool:
        return any(o.system == 'account_service' and o.category == 'USER_PROFILE' for o in observations)

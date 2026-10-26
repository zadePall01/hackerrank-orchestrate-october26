"""Grounded relationship, scoped consent, and policy applicability regressions."""
from pathlib import Path
from dataclasses import replace
import sys
import unittest
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit.contracts import AuditError
from audit.extract import Extractor,Scope
from audit.state import StateIndex
from audit.intent import authorizes_deletion
from audit.inputs import read_csv
from audit.policy import Policy
from test_audit import T0,T1,T2,request,identities,observation


class ResourceEdgeTests(unittest.TestCase):
    def index(self,event_time=T0,capture=T0,complete=True):
        ex=Extractor()
        ex.observations=[observation(category='SEARCH_INDEX_ENTRY',system='search_service',resource='search',captured=capture,attrs={'email':'person@example.invalid','source_resource_id':'account'})]
        ex.scopes=[Scope('snapshot',T1,T1,'account_service','USER_PROFILE',set(),'snapshot:customer_profiles',complete)]
        events=[dict(activity_id='route',event_time=event_time,event_type='DELETE_RECORD',resource_id='account',target_system='account_service',details='',reported_result='SUCCESS')]
        return StateIndex(ex,identities(),events)

    def test_explicit_edge_recovers_absent_account(self):
        records=self.index().resolve(request())
        account=next(o for o in records if o.resource=='account')
        self.assertEqual(account.state,'ABSENT')
        self.assertEqual(account.attributes['identity_link_evidence_id'],'proof')

    def test_future_link_not_used(self):
        with self.assertRaises(AuditError):self.index(capture='2026-02-01T00:00:00Z').resolve(request())

    def test_future_routing_not_used(self):
        self.assertEqual({o.resource for o in self.index(event_time='2026-02-01T00:00:00Z').resolve(request())},{'search'})

    def test_partial_scope_cannot_prove_absence(self):
        with self.assertRaises(AuditError):self.index(complete=False).resolve(request())

    def test_edge_does_not_hide_surviving_replica(self):
        index=self.index()
        replica=replace(observation(resource='account',attrs={'email':'other@example.invalid'}),scope='regional_replica')
        index.resources[('account_service','account')].append(replica)
        account=next(o for o in index.resolve(request()) if o.resource=='account')
        self.assertEqual(account.state,'PRESENT')

    def test_ambiguous_routing_does_not_guess(self):
        index=self.index();index.activity.append(dict(activity_id='other',event_time=T0,event_type='UPDATE_RECORD',resource_id='account',target_system='search_service',details=''))
        self.assertEqual({o.resource for o in index.resolve(request())},{'search'})


class ScopedConsentTests(unittest.TestCase):
    def test_multilingual_non_deletion(self):
        for text in ['Não solicito exclusão da conta; só quero uma cópia dos dados.','アカウントを削除しないでください。データのコピーだけを送ってください。','계정을 삭제하지 마세요. 정보 사본만 보내 주세요.']:
            with self.subTest(text=text):self.assertFalse(authorizes_deletion(text))

    def test_retention_exception_does_not_cancel_deletion(self):
        for text in ['Não apaguem os registros fiscais; excluam minha conta.','監査ログは削除しないでください。アカウントを削除してください。','감사 로그는 삭제하지 마세요. 계정을 삭제해 주세요.']:
            with self.subTest(text=text):self.assertTrue(authorizes_deletion(text))


class OwnershipFieldTests(unittest.TestCase):
    def test_export_owner_key_survives_correlated_log_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'read.log'
            path.write_text(f'{T0} level=DEBUG service=export_service trace_id=trace event=export_download_check_started owner_key="person@example.invalid"\n'
                            f'{T1} level=INFO service=export_service trace_id=trace event=export_download_check_completed resource_id=export available=false\n',encoding='utf-8')
            ex=Extractor();ex.log_file(dict(file_id='proof',captured_at=T1),path)
            records=StateIndex(ex,identities(),[]).resolve(request())
            self.assertEqual([(o.resource,o.state) for o in records],[('export','ABSENT')])

    def test_export_owner_key_does_not_join_another_subject(self):
        ex=Extractor();ex.observations=[observation(system='export_service',category='USER_EXPORT',attrs={'owner_key':'other@example.invalid'})]
        with self.assertRaises(AuditError):StateIndex(ex,identities(),[]).resolve(request())


class PolicyApplicabilityTests(unittest.TestCase):
    def policy(self):
        root=Path(__file__).resolve().parents[2]
        return Policy(read_csv(root/'dataset/deletion_rules.csv'))

    def test_retention_evaluated_at_audit_not_capture(self):
        obs=observation(category='SECURITY_AUDIT_LOG',system='security_service',attrs={'retention_until':T1})
        self.assertEqual(self.policy().applicability(obs,T0).status,'APPLICABLE')
        with self.assertRaises(AuditError):self.policy().assess(obs,T2)

    def test_unspecified_endpoint_abstains(self):
        obs=observation(category='SECURITY_AUDIT_LOG',system='security_service',attrs={'retention_until':T1})
        self.assertEqual(self.policy().applicability(obs,T1).status,'UNKNOWN')

    def test_missing_retention_is_not_silently_proved(self):
        obs=observation(category='SECURITY_AUDIT_LOG',system='security_service')
        self.assertEqual(self.policy().applicability(obs,T2).status,'UNKNOWN')

    def test_inactive_legal_hold_has_no_invented_delete(self):
        obs=observation(category='LEGAL_HOLD_RECORD',system='legal_service',attrs={'hold_active':False,'retained_until':'2030-01-01T00:00:00Z'})
        with self.assertRaises(AuditError):self.policy().assess(obs,T2)

    def test_future_hold_not_active(self):
        obs=observation(category='LEGAL_HOLD_RECORD',system='legal_service',attrs={'hold_starts_at':'2030-01-01T00:00:00Z','retained_until':'2035-01-01T00:00:00Z'})
        self.assertEqual(self.policy().applicability(obs,T2).status,'INAPPLICABLE')

    def test_shared_attachment_not_deleted_under_subject_only_rule(self):
        obs=observation(category='SUPPORT_ATTACHMENT',system='support_platform',attrs={'subject_only':False})
        with self.assertRaises(AuditError):self.policy().assess(obs,T2)

    def test_subject_only_attachment_and_shared_ticket_apply(self):
        self.assertEqual(self.policy().applicability(observation(category='SUPPORT_ATTACHMENT',attrs={'subject_only':True}),T2).status,'APPLICABLE')
        self.assertEqual(self.policy().applicability(observation(category='SUPPORT_MESSAGE',attrs={'ticket_id':'CS-1'}),T2).status,'APPLICABLE')

    def test_active_account_not_treated_as_deleted_tombstone(self):
        with self.assertRaises(AuditError):self.policy().assess(observation(category='ACCOUNT_TOMBSTONE',attrs={'account_status':'ACTIVE','user_id':'subject'}),T2)

    def test_bad_interval_is_controlled_error(self):
        with self.assertRaises(AuditError):self.policy().assess(observation(category='SECURITY_AUDIT_LOG',attrs={'retention_until':'invalid'}),T2)

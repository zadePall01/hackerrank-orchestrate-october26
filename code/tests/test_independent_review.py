"""Independent regression cases derived from specification violations."""
from __future__ import annotations
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest
import importlib.util
import json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from audit.contracts import AuditError
from audit.contracts import validate_output
from audit.extract import Extractor, Scope, infer_state
from audit.state import StateIndex
from audit.planner import plan
from audit.intent import authorizes_deletion
from test_audit import T0,T1,T2,identities,request,observation
from test_audit import policy


class RestoreReviewTests(unittest.TestCase):
    def test_explicit_restore_denial_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'readback.log'
            path.write_text(f'{T0} level=INFO service=backup_service event=restore_authorization_completed resource_id=archive decision=deny policy=privacy_deletion\n',encoding='utf-8')
            ex=Extractor(); ex.log_file(dict(file_id='proof',captured_at=T0),path)
            self.assertEqual(ex.observations[0].state,'BLOCKED')

    def test_missing_restore_decision_is_not_default_allow(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'readback.log'
            path.write_text(f'{T0} level=INFO service=backup_service event=restore_authorization_completed resource_id=archive\n',encoding='utf-8')
            with self.assertRaises(AuditError): Extractor().log_file(dict(file_id='proof',captured_at=T0),path)


class ReplicaReviewTests(unittest.TestCase):
    def test_newer_primary_absence_cannot_clear_replica(self):
        ex=Extractor()
        replica=replace(observation(),scope='proof:account_service:regional_replica')
        primary=observation(state='ABSENT',observed=T1,captured=T1,evidence='primary')
        ex.observations=[replica,primary]
        self.assertEqual(StateIndex(ex,identities(),[]).resolve(request())[0].state,'PRESENT')

    def test_newer_read_of_same_replica_can_clear_it(self):
        ex=Extractor()
        old=replace(observation(),scope='old:account_service:regional_replica')
        cleared=replace(observation(state='ABSENT',observed=T1,captured=T1,evidence='cleared'),scope='new:account_service:regional_replica')
        ex.observations=[old,cleared]
        self.assertEqual(StateIndex(ex,identities(),[]).resolve(request())[0].state,'ABSENT')

    def test_partial_json_collection_cannot_prove_absence(self):
        ex=Extractor()
        ex.observations=[observation(),observation(category='SUPPORT_MESSAGE',state='REDACTED',resource='ticket',system='support_platform',evidence='partial',observed=T1,captured=T1)]
        ex.scopes=[Scope('partial',T1,T1,'account_service','USER_PROFILE',set(),'partial:customer_profiles')]
        account=next(o for o in StateIndex(ex,identities(),[]).resolve(request()) if o.system=='account_service')
        self.assertEqual(account.state,'PRESENT')


class CoverageReviewTests(unittest.TestCase):
    def test_grounded_search_violation_does_not_require_invented_account(self):
        ex=Extractor(); ex.observations=[observation(category='SEARCH_INDEX_ENTRY',system='search_service',resource='search')]
        resources=StateIndex(ex,identities(),[]).resolve(request())
        result=plan('fixture',resources,policy())
        self.assertEqual(result['deletion_status'],'INCOMPLETE')
        self.assertEqual({s['resource_id'] for s in __import__('json').loads(result['steps_json'])},{'search'})


class ContradictionReviewTests(unittest.TestCase):
    def test_redacted_label_does_not_override_exposed_email(self):
        self.assertEqual(infer_state('SUPPORT_MESSAGE',{'result':'REDACTED','email':'person@example.invalid'}),'PRESENT')

    def test_anonymized_label_does_not_override_stable_user_link(self):
        self.assertEqual(infer_state('ANALYTICS_PROFILE',{'result':'ANONYMIZED','user_id':'subject'}),'PRESENT')

    def test_restore_flag_overrides_conflicting_result_label(self):
        self.assertEqual(infer_state('BACKUP_ARCHIVE',{'result':'BLOCKED','restore_allowed':True}),'ACTIVE')

    def test_unknown_boolean_is_not_inferred_active(self):
        with self.assertRaises(AuditError): infer_state('DATA_FLOW',{'enabled':'maybe'})

    def test_phone_in_message_requires_redaction(self):
        self.assertEqual(infer_state('SUPPORT_MESSAGE',{'requester_email':None,'message_text':'Call me at +1 (212) 555-0199.'}),'PRESENT')


class IntentReviewTests(unittest.TestCase):
    def test_how_to_question_is_not_authorization(self):
        self.assertFalse(authorizes_deletion('How do I delete my account?'))

    def test_quoted_request_is_not_authorization(self):
        self.assertFalse(authorizes_deletion('Send me a copy of the message that says "delete my account".'))

    def test_retention_exception_does_not_cancel_account_deletion(self):
        self.assertTrue(authorizes_deletion('Do not delete my invoices; please delete my account.'))


class EvaluatorReviewTests(unittest.TestCase):
    def test_duplicate_steps_penalize_field_accuracy(self):
        source=Path(__file__).resolve().parents[1]/'evaluation/main.py'
        spec=importlib.util.spec_from_file_location('review_evaluator',source)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        truth=plan('fixture',[observation(state='ABSENT')],policy())
        steps=json.loads(truth['steps_json']); duplicate=dict(steps[0],step_no=2)
        prediction=dict(truth,steps_json=json.dumps(steps+[duplicate]))
        self.assertEqual(module.metrics([prediction],[truth])['field_accuracy'],0.5)

    def test_primitive_step_is_a_schema_error(self):
        row=dict(case_id='fixture',deletion_status='COMPLETE',steps_json='[123]')
        with self.assertRaises(AuditError): validate_output([row],[request()],{'proof':T0})

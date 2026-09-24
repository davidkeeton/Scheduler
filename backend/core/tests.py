import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from django.core.management import call_command
from django.test import TestCase, override_settings
from core.models import Team, Employee, CoverageSlot, Shift, Publication, Callout
from core.scheduling_rules import placement_issue
from core.views import demand_coverage


class SchedulingRulesTests(TestCase):
    def test_work_and_standby_are_distinct(self):
        t = datetime(2026, 9, 21, tzinfo=timezone.utc)
        slot = lambda a, b, mode: SimpleNamespace(start=t+timedelta(hours=a), end=t+timedelta(hours=b), mode=mode)
        self.assertIsNone(placement_issue(slot(12, 24, 'on_call'), [slot(0, 12, 'staffed')]))
        self.assertIn('stacking', placement_issue(slot(8, 16, 'staffed'), [slot(0, 8, 'staffed')]))
        self.assertIn('stacking', placement_issue(slot(8, 16, 'on_call'), [slot(0, 8, 'on_call')]))
        self.assertIn('8 hours', placement_issue(slot(14, 22, 'staffed'), [slot(0, 8, 'staffed')]))

    def test_one_shift_spans_two_coverage_periods(self):
        team = Team.objects.create(key='a', name='A', skill='a')
        person = Employee.objects.create(key='1', name='A', phone='', team=team, classification='casual', skills=['a'])
        start = datetime(2026, 9, 21, tzinfo=timezone.utc)
        shift = Shift(employee=person, team=team, start=start, end=start+timedelta(hours=8), mode='staffed')
        for offset in (0, 4):
            demand = CoverageSlot(team=team, start=start+timedelta(hours=offset), end=start+timedelta(hours=offset+4), mode='staffed', required=1, required_skill='a')
            self.assertEqual((1, 240), demand_coverage(demand, [shift]))


@override_settings(ALPHA_AUTO_ADMIN=True, ALLOWED_HOSTS=['testserver'])
class SchedulingApiTests(TestCase):
    def setUp(self):
        call_command('seed_pilot', verbosity=0)

    def post(self, path, data):
        return self.client.post('/api/'+path, data=json.dumps(data), content_type='application/json')

    def test_draft_edit_publish_lookup(self):
        week = '2026-09-21'
        response = self.post('generate', {'week': week})
        self.assertEqual(200, response.status_code)
        state = response.json()
        self.assertTrue(state['coverage'])
        self.assertTrue(state['shifts'])
        person = state['employees'][0]
        result = self.post('person', {**person, 'phone': '604-555-9999', 'week': week})
        self.assertEqual(200, result.status_code)
        self.assertEqual(week, result.json()['week'])
        self.assertEqual(200, self.post('publish', {'week': week}).status_code)
        lookup = self.client.get('/api/oncall?team=team-1&at=2026-09-21T08:00:00Z')
        self.assertEqual(200, lookup.status_code)
        self.assertTrue(lookup.json()['people'])

    def test_oncall_lists_staffed_and_standby_contacts_in_time_order(self):
        team = Team.objects.get(key='team-1')
        employee = Employee.objects.filter(team=team).first()
        start = datetime(2027, 1, 1, tzinfo=timezone.utc)
        Shift.objects.create(employee=employee, team=team, start=start, end=start+timedelta(hours=8), mode='staffed', batch='published', published=True)
        Shift.objects.create(employee=employee, team=team, start=start+timedelta(hours=8), end=start+timedelta(hours=16), mode='on_call', batch='published', published=True)
        response = self.client.get('/api/oncall?team=team-1&at=2027-01-01T01:00:00Z')
        self.assertEqual(200, response.status_code)
        people = response.json()['people']
        self.assertEqual(['staffed', 'on_call'], [person['mode'] for person in people[:2]])
        self.assertTrue(people[0]['current'])
        self.assertFalse(people[1]['current'])

    def test_generating_another_week_preserves_first_draft(self):
        first = '2026-09-21'
        second = '2026-09-28'
        self.assertEqual(200, self.post('generate', {'week': first}).status_code)
        first_count = CoverageSlot.objects.filter(batch='draft', start__gte=datetime(2026,9,21,tzinfo=timezone.utc), start__lt=datetime(2026,9,28,tzinfo=timezone.utc)).count()
        self.assertGreater(first_count, 0)
        self.assertEqual(200, self.post('generate', {'week': second}).status_code)
        self.assertEqual('draft', self.client.get('/api/state?week='+first).json()['batch'])
        self.assertEqual('draft', self.client.get('/api/state?week='+second).json()['batch'])

    def test_publication_revisions_and_week_navigation(self):
        week = '2026-09-21'
        self.assertEqual(200, self.post('generate', {'week': week}).status_code)
        self.assertEqual(200, self.post('publish', {'week': week}).status_code)
        self.assertEqual(200, self.post('generate', {'week': week}).status_code)
        self.assertEqual(200, self.post('publish', {'week': week}).status_code)
        self.assertEqual([2, 1], [v['revision'] for v in self.client.get('/api/history?week='+week).json()['versions']])
        self.assertIn(week, self.client.get('/api/state?week='+week).json()['published_weeks'])
        self.assertEqual(2, Publication.objects.filter(week=week).count())

    def test_absence_blocks_publish_and_callout_survives_shift_replacement(self):
        week = '2026-09-21'
        self.post('generate', {'week': week})
        self.post('publish', {'week': week})
        standby = Shift.objects.filter(batch='published', mode='on_call').first()
        call = self.post('callout', {'shift': standby.id, 'start': standby.start.isoformat(), 'end': (standby.start+timedelta(hours=1)).isoformat()})
        self.assertEqual(200, call.status_code)
        Shift.objects.filter(pk=standby.id).delete()
        self.assertTrue(Callout.objects.filter(standby_shift__isnull=True, employee_key=standby.employee.key).exists())
        self.post('generate', {'week': week})
        item = Shift.objects.filter(batch='draft').first()
        absent = self.post('absence', {'employee': item.employee.key, 'start': item.start.isoformat(), 'end': item.end.isoformat(), 'kind': 'sick'})
        self.assertEqual(200, absent.status_code)
        self.assertTrue(absent.json()['absences'][0]['affected'])
        blocked = self.post('publish', {'week': week})
        self.assertEqual(409, blocked.status_code)
        self.assertIn(item.id, [x['id'] for x in blocked.json()['blocked_shifts']])

    def test_publish_identifies_both_conflicting_shift_cards(self):
        week = '2026-09-21'
        response = self.post('generate', {'week': week})
        self.assertEqual(200, response.status_code)
        first = Shift.objects.filter(batch='draft', mode='staffed').first()
        second = Shift.objects.create(employee=first.employee, team=first.team,
                                      start=first.start, end=first.end,
                                      mode=first.mode, batch='draft')
        blocked = self.post('publish', {'week': week})
        self.assertEqual(409, blocked.status_code)
        ids = {item['id'] for item in blocked.json()['blocked_shifts']}
        self.assertTrue({first.id, second.id}.issubset(ids))
        self.assertIn('overlapping', next(item['reason'] for item in blocked.json()['blocked_shifts'] if item['id'] == first.id))
        self.assertFalse(Shift.objects.filter(pk=first.id, published=True).exists())

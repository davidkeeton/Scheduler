import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo
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

    def test_blank_week_lists_previous_source_and_accepts_copy_into_it(self):
        source = '2026-09-21'
        target = '2026-10-12'
        self.assertEqual(200, self.post('generate', {'week': source}).status_code)
        blank = self.client.get('/api/state?week='+target).json()
        self.assertFalse(blank['coverage'])
        self.assertFalse(blank['shifts'])
        self.assertIn({'week': source, 'batch': 'draft'}, blank['source_weeks'])
        preview = self.post('copy-week', {'source_week': source, 'target_week': target, 'preview': True})
        self.assertEqual(200, preview.status_code)
        self.assertEqual(target, preview.json()['target_week'])
        applied = self.post('copy-week', {'source_week': source, 'target_week': target})
        self.assertEqual(200, applied.status_code)
        self.assertEqual(target, applied.json()['week'])
        self.assertTrue(applied.json()['coverage'])
        self.assertTrue(applied.json()['shifts'])

    def test_repeat_preview_detects_boundary_conflicts_between_new_weeks(self):
        local = ZoneInfo('America/Vancouver')
        team = Team.objects.get(key='team-1')
        person = next(e for e in Employee.objects.filter(team=team) if team.skill in e.skills)
        monday = datetime(2026,9,21,0,tzinfo=local)
        sunday = datetime(2026,9,27,16,tzinfo=local)
        for start,end in ((monday,monday+timedelta(hours=8)),(sunday,sunday+timedelta(hours=8))):
            Shift.objects.create(team=team,employee=person,start=start,end=end,mode='on_call',batch='published',published=True)
            CoverageSlot.objects.create(team=team,start=start,end=end,mode='on_call',required=1,required_skill=team.skill,batch='published')
        result = self.post('copy-week',{'source_week':'2026-09-21','target_week':'2026-09-28','interval':'week','count':2,'preview':True})
        self.assertEqual(200,result.status_code)
        self.assertTrue(any('between copied weeks' in x['reason'] for x in result.json()['issues']))
        self.assertFalse(Shift.objects.filter(batch='draft').exists())

    def test_repeat_copy_is_atomic_and_respects_existing_drafts(self):
        source = '2026-09-21'
        self.post('generate', {'week': source})
        self.post('generate', {'week': '2026-10-05'})
        payload = {'source_week':source, 'target_week':'2026-09-28', 'interval':'week', 'every':1, 'count':3}
        preview = self.post('copy-week', {**payload, 'preview':True})
        self.assertEqual(200, preview.status_code)
        self.assertEqual(['2026-09-28','2026-10-05','2026-10-12'], [t['target_week'] for t in preview.json()['targets']])
        self.assertTrue(preview.json()['targets'][1]['target_has_draft'])
        rejected = self.post('copy-week', payload)
        self.assertEqual(409, rejected.status_code)
        self.assertFalse(CoverageSlot.objects.filter(batch='draft',start__gte=datetime(2026,9,28,tzinfo=timezone.utc),start__lt=datetime(2026,10,5,tzinfo=timezone.utc)).exists())
        applied = self.post('copy-week', {**payload,'replace':True})
        self.assertEqual(200, applied.status_code)
        self.assertEqual(3, applied.json()['copy_summary']['count'])
        for week in ('2026-09-28','2026-10-05','2026-10-12'):
            self.assertEqual('draft', self.client.get('/api/state?week='+week).json()['batch'])
        self.assertEqual('draft', self.client.get('/api/state?week='+source).json()['batch'])

    def test_conflict_resolver_lists_eligible_people_and_rechecks_assignment(self):
        week = '2026-09-21'
        self.post('generate', {'week':week})
        item = Shift.objects.filter(batch='draft',mode='staffed').select_related('employee','team').first()
        self.post('absence',{'employee':item.employee.key,'start':item.start.isoformat(),'end':item.end.isoformat(),'kind':'sick'})
        result = self.client.get('/api/conflicts?week='+week)
        self.assertEqual(200,result.status_code)
        conflict = next(c for c in result.json()['conflicts'] if c['id']==item.id)
        self.assertIn('unavailable',conflict['reason'])
        candidates = conflict['candidates']
        self.assertTrue(candidates)
        self.assertTrue(all(candidates[i]['home_team_first'] or not candidates[i+1]['home_team_first'] for i in range(len(candidates)-1)))
        rejected = self.post('resolve-conflict',{'week':week,'shift_id':item.id,'employee':'not-a-person'})
        self.assertEqual(409,rejected.status_code)
        applied = self.post('resolve-conflict',{'week':week,'shift_id':item.id,'employee':candidates[0]['key']})
        self.assertEqual(200,applied.status_code)
        item.refresh_from_db()
        self.assertEqual(candidates[0]['key'],item.employee.key)

    def test_resolver_can_report_no_eligible_replacement(self):
        team = Team.objects.create(key='sole',name='Sole',skill='only-one')
        person = Employee.objects.create(key='sole-person',name='Sole Person',phone='',team=team,classification='full_time',skills=['only-one'])
        start = datetime(2026,9,21,16,tzinfo=timezone.utc)
        shift = Shift.objects.create(team=team,employee=person,start=start,end=start+timedelta(hours=8),mode='staffed',batch='draft')
        self.post('absence',{'employee':person.key,'start':start.isoformat(),'end':(start+timedelta(hours=8)).isoformat(),'kind':'sick'})
        conflict = next(c for c in self.client.get('/api/conflicts?week=2026-09-21').json()['conflicts'] if c['id']==shift.id)
        self.assertEqual([],conflict['candidates'])

    def test_copy_week_preserves_local_times_details_and_existing_drafts(self):
        local = ZoneInfo('America/Vancouver')
        team = Team.objects.get(key='team-1')
        employee = next(e for e in Employee.objects.filter(team=team) if team.skill in e.skills)
        start = datetime(2026, 10, 26, 8, 0, tzinfo=local)
        end = datetime(2026, 10, 26, 16, 0, tzinfo=local)
        CoverageSlot.objects.create(team=team, start=start, end=end, mode='staffed', required=1, required_skill=team.skill, batch='published')
        Shift.objects.create(team=team, employee=employee, start=start, end=end, mode='staffed', batch='published', published=True, location='Depot', role='Lead', notes='Handoff', break_minutes=30)
        payload = {'source_week':'2026-10-26','target_week':'2026-11-02'}
        preview = self.post('copy-week', {**payload, 'preview': True})
        self.assertEqual(200, preview.status_code)
        self.assertEqual((1,1), (preview.json()['coverage'],preview.json()['shifts']))
        self.assertFalse(Shift.objects.filter(batch='draft').exists())
        copied = self.post('copy-week', payload)
        self.assertEqual(200, copied.status_code)
        item = Shift.objects.get(batch='draft')
        self.assertEqual((2026,11,2,8), (item.start.astimezone(local).year,item.start.astimezone(local).month,item.start.astimezone(local).day,item.start.astimezone(local).hour))
        self.assertEqual((item.location,item.role,item.notes,item.break_minutes),('Depot','Lead','Handoff',30))
        self.assertNotEqual(start.utcoffset(), item.start.astimezone(local).utcoffset())  # DST changes UTC offset
        self.assertEqual(409,self.post('copy-week',payload).status_code)
        self.assertEqual(200,self.post('copy-week',{**payload,'replace':True}).status_code)
        self.assertEqual(1,Shift.objects.filter(batch='draft').count())
        self.assertEqual(1,Shift.objects.filter(batch='published').count())

    def test_copy_preview_flags_absence_without_mutating_target(self):
        self.post('generate',{'week':'2026-09-21'})
        person = Shift.objects.filter(batch='draft').first().employee
        self.post('absence',{'employee':person.key,'start':'2026-09-28T00:00:00Z','end':'2026-10-05T00:00:00Z','kind':'vacation'})
        result = self.post('copy-week',{'source_week':'2026-09-21','target_week':'2026-09-28','preview':True})
        self.assertEqual(200,result.status_code)
        self.assertTrue(any(x['employee']==person.name and 'unavailable' in x['reason'] for x in result.json()['issues']))
        self.assertFalse(Shift.objects.filter(batch='draft',start__gte=datetime(2026,9,28,tzinfo=timezone.utc)).exists())
        applied = self.post('copy-week',{'source_week':'2026-09-21','target_week':'2026-09-28'})
        self.assertEqual(200, applied.status_code)
        self.assertTrue(all(item['id'] is not None for item in applied.json()['blocked_shifts']))
        self.assertEqual(409, self.post('publish',{'week':'2026-09-28'}).status_code)

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

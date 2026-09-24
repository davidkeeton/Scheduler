import json
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction
from django.db.models import Q, Max
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Team, Employee, CoverageSlot, Shift, Publication, ScheduleEvent, Absence, Callout
from core.scheduling_rules import placement_issue, schedule_advisories

PACIFIC = ZoneInfo('America/Vancouver')

def error(message, status=400):
    return JsonResponse({'error': message}, status=status)

def body(request):
    try:
        return json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return None

def admin_post(request):
    return request.method == 'POST' and settings.ALPHA_AUTO_ADMIN

def utc(day, hour):
    return datetime.combine(day + timedelta(days=hour // 24), time.min, PACIFIC).replace(hour=hour % 24).astimezone(timezone.utc)

def week_bounds(value):
    day = date.fromisoformat(value)
    monday = day - timedelta(days=day.weekday())
    return monday, utc(monday, 0), utc(monday + timedelta(days=7), 0)

def event_week(day):
    return day-timedelta(days=day.weekday())

def parsed_time(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Time zone required')
    return result.astimezone(timezone.utc)

def demand_coverage(slot, shifts):
    relevant = [s for s in shifts if s.team_id == slot.team_id and s.mode == slot.mode and (slot.required_skill or slot.team.skill) in s.employee.skills and s.start < slot.end and s.end > slot.start]
    cuts = sorted({slot.start, slot.end, *(max(s.start, slot.start) for s in relevant), *(min(s.end, slot.end) for s in relevant)})
    minimum = min((len({s.employee_id for s in relevant if s.start <= a and s.end >= b}) for a, b in zip(cuts, cuts[1:])), default=0)
    covered_minutes = sum((b-a).total_seconds()/60 for a, b in zip(cuts, cuts[1:]) if len({s.employee_id for s in relevant if s.start <= a and s.end >= b}) >= slot.required)
    return minimum, round(covered_minutes)

def callout_rest_issues(shifts, beginning, ending):
    """Flag worked assignments too close to recorded actual call-out work."""
    records = list(Callout.objects.filter(start__lt=ending+timedelta(days=2), end__gt=beginning-timedelta(days=2)))
    issues = {}
    for shift in shifts:
        if shift.mode != 'staffed': continue
        for call in records:
            if call.employee_key != shift.employee.key: continue
            if call.start < shift.end and call.end > shift.start:
                issues[shift.id] = 'Worked shift overlaps recorded call-out work'
            elif timedelta(0) <= shift.start-call.end < timedelta(hours=8) or timedelta(0) <= call.start-shift.end < timedelta(hours=8):
                issues[shift.id] = 'Less than 8 hours between a worked shift and recorded call-out work'
    return issues

def state(request):
    try:
        monday, beginning, ending = week_bounds(request.GET.get('week') or date.today().isoformat())
    except ValueError:
        return error('Invalid week date')
    has_draft = CoverageSlot.objects.filter(batch='draft', start__gte=beginning, start__lt=ending).exists() or Shift.objects.filter(batch='draft', start__gte=beginning, start__lt=ending).exists()
    batch = 'draft' if has_draft else 'published'
    slots = list(CoverageSlot.objects.filter(batch=batch, start__lt=ending, end__gt=beginning).select_related('team').order_by('start', 'team__key'))
    shifts = list(Shift.objects.filter(batch=batch, start__lt=ending, end__gt=beginning).select_related('employee', 'team').order_by('start', 'team__key'))
    coverage = []
    for s in slots:
        covered, minutes = demand_coverage(s, shifts)
        coverage.append({'id': s.id, 'team': s.team.key, 'start': s.start.isoformat(), 'end': s.end.isoformat(), 'mode': s.mode, 'required': s.required, 'skill': s.required_skill or s.team.skill, 'weight': float(s.weight), 'covered': covered, 'covered_minutes': minutes, 'total_minutes': round((s.end-s.start).total_seconds()/60)})
    notices = schedule_advisories(shifts, beginning, ending)
    names = {e.id: e.name for e in Employee.objects.all()}
    rest_issues = callout_rest_issues(shifts, beginning, ending)
    notices += [{'code': 'callout_rest', 'employee_id': s.employee_id, 'message': rest_issues[s.id]} for s in shifts if s.id in rest_issues]
    published_weeks = sorted({(d.astimezone(PACIFIC).date()-timedelta(days=d.astimezone(PACIFIC).weekday())).isoformat() for d in CoverageSlot.objects.filter(batch='published').values_list('start', flat=True)} | {w.isoformat() for w in Publication.objects.values_list('week', flat=True)})
    revisions = list(Publication.objects.filter(week=monday).values('id','revision','created_at','actor').order_by('-revision'))
    absences = [{'id': a.id, 'employee': a.employee.key, 'name': a.employee.name, 'start': a.start.isoformat(), 'end': a.end.isoformat(), 'kind': a.kind, 'note': a.note, 'affected': [s.id for s in shifts if s.employee_id == a.employee_id and s.start < a.end and s.end > a.start]} for a in Absence.objects.filter(start__lt=ending, end__gt=beginning).select_related('employee')]
    callouts = [{'id': c.id, 'shift': c.standby_shift_id, 'employee': c.employee_name, 'start': c.start.isoformat(), 'end': c.end.isoformat(), 'note': c.note} for c in Callout.objects.filter(start__lt=ending, end__gt=beginning).select_related('standby_shift__employee')]
    return JsonResponse({'week': monday.isoformat(), 'published_weeks': published_weeks, 'revisions': revisions, 'absences': absences, 'callouts': callouts, 'batch': batch, 'timezone': 'America/Vancouver', 'rule_profile': 'BC pilot; home/mobile standby assumed', 'advisories': [{'code': n['code'], 'message': f"{names.get(n['employee_id'], 'Employee')}: {n['message']}"} for n in notices],
        'teams': [{'key': t.key, 'name': t.name, 'skill': t.skill, 'coverage_template': t.coverage_template, 'preferences': t.preferences} for t in Team.objects.order_by('key')],
        'employees': [{'key': e.key, 'name': e.name, 'phone': e.phone, 'team': e.team.key, 'classification': e.classification, 'skills': e.skills, 'preferences': e.preferences, 'availability': e.availability, 'available_windows': e.available_windows} for e in Employee.objects.select_related('team').order_by('key')],
        'coverage': coverage, 'shifts': [{'id': s.id, 'employee': s.employee.key, 'team': s.team.key, 'start': s.start.isoformat(), 'end': s.end.isoformat(), 'mode': s.mode, 'published': s.published, 'cross_team': s.employee.team_id != s.team_id, 'break_minutes': s.break_minutes, 'location': s.location, 'role': s.role, 'notes': s.notes} for s in shifts]})

def make_week_coverage(monday):
    for team in Team.objects.all():
        for offset in range(7):
            day = monday + timedelta(days=offset)
            for rule in team.coverage_template:
                if offset in rule.get('days', []):
                    CoverageSlot.objects.create(team=team, start=utc(day, int(rule['start'])), end=utc(day, int(rule['end'])), mode=rule['mode'], required=int(rule.get('required', 1)), required_skill=team.skill, weight=Decimal(str(rule.get('weight', .8))), batch='draft')

@csrf_exempt
def generate(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    try: monday, beginning, ending = week_bounds(data['week'])
    except (ValueError, KeyError, TypeError): return error('Valid week required')
    with transaction.atomic():
        CoverageSlot.objects.filter(batch='draft', start__gte=beginning, start__lt=ending).delete()
        Shift.objects.filter(batch='draft', start__gte=beginning, start__lt=ending).delete()
        published = list(CoverageSlot.objects.filter(batch='published', start__gte=beginning, start__lt=ending))
        if published:
            for s in published:
                CoverageSlot.objects.create(team=s.team, start=s.start, end=s.end, mode=s.mode, required=s.required, required_skill=s.required_skill, weight=s.weight, priority=s.priority, batch='draft')
            for s in Shift.objects.filter(batch='published', start__gte=beginning, start__lt=ending):
                Shift.objects.create(team=s.team, employee=s.employee, start=s.start, end=s.end, mode=s.mode, batch='draft', break_minutes=s.break_minutes, location=s.location, role=s.role, notes=s.notes)
        else:
            make_week_coverage(monday)
            employees = list(Employee.objects.select_related('team'))
            shifts = {e.id: list(Shift.objects.filter(employee=e, batch='published').exclude(start__gte=beginning, start__lt=ending)) for e in employees}
            hours = {e.id: 0 for e in employees}
            windows = list(CoverageSlot.objects.filter(batch='draft').select_related('team').order_by('-weight', 'start'))
            for slot in windows:
                for _ in range(slot.required):
                    proposal = Shift(team=slot.team, start=slot.start, end=slot.end, mode=slot.mode, batch='draft')
                    candidates = [e for e in employees if (slot.required_skill or slot.team.skill) in e.skills and not unavailable(e, proposal) and not placement_issue(proposal, shifts[e.id])]
                    if not candidates: break
                    candidates.sort(key=lambda e: (e.team_id != slot.team_id, preference_cost(e, proposal, shifts[e.id]) + hours[e.id]/20, hours[e.id], e.key))
                    employee = candidates[0]
                    proposal.employee = employee
                    proposal.save()
                    shifts[employee.id].append(proposal)
                    hours[employee.id] += (slot.end-slot.start).total_seconds()/3600
    ScheduleEvent.objects.create(action='draft_generated', week=monday, detail={'from_published': bool(published)})
    return state_with_week(request, monday)

def preference_cost(employee, proposed, existing):
    """Soft ranking: a matching day/night block or weekend slot is preferred."""
    preference = {**employee.team.preferences, **employee.preferences}
    local = proposed.start.astimezone(PACIFIC)
    is_night = local.hour < 7 or local.hour >= 19
    cost = 0
    if preference.get('shift_type') == 'days' and is_night: cost += 3
    if preference.get('shift_type') == 'nights' and not is_night: cost += 3
    if preference.get('day_night') == 'consistent' and existing:
        latest = max(existing, key=lambda s: s.end)
        previous_hour = latest.start.astimezone(PACIFIC).hour
        if (previous_hour < 7 or previous_hour >= 19) != is_night: cost += 1
    if proposed.mode == 'on_call':
        related = [s for s in existing if s.mode == 'on_call' and s.start.astimezone(PACIFIC).hour == local.hour and 0 < abs((s.start-proposed.start).total_seconds()) <= 48*3600]
        matching = bool(related)
        target = preference.get('block_length')
        target = target if isinstance(target, int) and 1 <= target <= 14 else 2
        if preference.get('on_call_grouping', 'paired') == 'paired' and matching and len(related) < target: cost -= 2
        if preference.get('on_call_grouping') == 'isolated' and matching: cost += 2
        if preference.get('weekend_continuity') and local.weekday() == 6 and matching: cost -= 1
    return cost

def unavailable(employee, proposed):
    # Casual availability is positive: once any periods are supplied, an entire
    # proposed shift must fit inside their union. Empty retains alpha behavior.
    if employee.classification == 'casual' and employee.available_windows:
        intervals = sorted((parsed_time(p['start']), parsed_time(p['end'])) for p in employee.available_windows)
        cursor = proposed.start
        for start, end in intervals:
            if start <= cursor < end: cursor = max(cursor, end)
            if cursor >= proposed.end: break
        if cursor < proposed.end:
            return True
    if Absence.objects.filter(employee=employee, start__lt=proposed.end, end__gt=proposed.start).exists(): return True
    for period in employee.availability:
        try:
            if parsed_time(period['start']) < proposed.end and parsed_time(period['end']) > proposed.start: return True
        except (KeyError, ValueError): continue
    return False

def state_with_week(request, monday):
    request.GET = request.GET.copy()
    request.GET['week'] = monday.isoformat() if hasattr(monday, 'isoformat') else str(monday)
    return state(request)

@csrf_exempt
def coverage(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    if data is None: return error('Invalid JSON')
    try:
        if data.get('id'):
            slot = CoverageSlot.objects.get(pk=data['id'], batch='draft')
            if data.get('delete'):
                week = slot.start.astimezone(PACIFIC).date()
                slot.delete()
                ScheduleEvent.objects.create(action='coverage_deleted', week=event_week(week), detail={'coverage_id': data['id']})
                return state_with_week(request, week)
        else:
            slot = CoverageSlot(batch='draft')
        slot.team = Team.objects.get(key=data['team'])
        slot.start, slot.end = parsed_time(data['start']), parsed_time(data['end'])
        slot.mode = data['mode']
        slot.required = int(data['required'])
        slot.weight = Decimal(str(data['weight']))
        slot.required_skill = data.get('skill') or slot.team.skill
        if slot.start >= slot.end or (slot.end-slot.start) > timedelta(hours=24) or slot.mode not in ('staffed','on_call') or not 0 <= slot.required <= 20 or not Decimal('.01') <= slot.weight <= Decimal('1'): raise ValueError()
        slot.save()
        ScheduleEvent.objects.create(action='coverage_saved', week=event_week(slot.start.astimezone(PACIFIC).date()), detail={'coverage_id': slot.id})
    except (KeyError, ValueError, TypeError, ArithmeticError, Team.DoesNotExist, CoverageSlot.DoesNotExist): return error('Invalid draft coverage: check team, times, headcount and weight')
    return state_with_week(request, slot.start.astimezone(PACIFIC).date())

@csrf_exempt
def shift(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    if data is None: return error('Invalid JSON')
    try:
        if data.get('id'):
            item = Shift.objects.get(pk=data['id'], batch='draft')
            if data.get('delete'):
                week = item.start.astimezone(PACIFIC).date()
                item.delete()
                ScheduleEvent.objects.create(action='shift_deleted', week=event_week(week), detail={'shift_id': data['id']})
                return state_with_week(request, week)
        else: item = Shift(batch='draft')
        item.employee = Employee.objects.get(key=data['employee'])
        item.team = Team.objects.get(key=data['team'])
        item.start, item.end = parsed_time(data['start']), parsed_time(data['end'])
        item.mode = data['mode']
        item.break_minutes = int(data.get('break_minutes', 0))
        item.location = str(data.get('location', '')).strip()
        item.role = str(data.get('role', '')).strip()
        item.notes = str(data.get('notes', '')).strip()
        if item.start >= item.end or item.end-item.start > timedelta(hours=24) or item.mode not in ('staffed','on_call') or not 0 <= item.break_minutes < (item.end-item.start).total_seconds()/60 or len(item.location)>100 or len(item.role)>80 or len(item.notes)>500: raise ValueError()
        if item.team.skill not in item.employee.skills: return error('Employee lacks the team qualification')
        if unavailable(item.employee, item): return error('Employee is unavailable during this shift')
        monday, beginning, ending = week_bounds(item.start.astimezone(PACIFIC).date().isoformat())
        peers = list(Shift.objects.filter(employee=item.employee, batch='draft').exclude(pk=item.pk))
        peers += list(Shift.objects.filter(employee=item.employee, batch='published').exclude(start__gte=beginning, start__lt=ending))
        issue = placement_issue(item, peers)
        if issue: return error(issue)
        item.save()
        ScheduleEvent.objects.create(action='shift_saved', week=monday, detail={'shift_id': item.id, 'employee': item.employee.key})
    except (KeyError, ValueError, TypeError, Shift.DoesNotExist, Employee.DoesNotExist, Team.DoesNotExist): return error('Invalid draft shift: check person, team and times')
    return state_with_week(request, item.start.astimezone(PACIFIC).date())

@csrf_exempt
def team(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    if data is None: return error('Invalid JSON')
    try:
        key = str(data['key']).strip()
        if not key or len(key) > 40: raise ValueError()
        name, skill = str(data['name']).strip(), str(data['skill']).strip()
        if not name or not skill: raise ValueError()
        preferences = data.get('preferences', {})
        template = data.get('coverage_template', [])
        if not isinstance(preferences, dict) or not isinstance(template, list): raise ValueError()
        for r in template:
            if (not isinstance(r.get('days'), list) or any(d not in range(7) for d in r['days']) or not 0 <= int(r['start']) < int(r['end']) <= 24 or r['mode'] not in ('staffed','on_call') or not 0 <= int(r.get('required',1)) <= 20 or not .01 <= float(r.get('weight',.8)) <= 1): raise ValueError()
        record, _ = Team.objects.get_or_create(key=key, defaults={'name': name, 'skill': skill})
        record.name, record.skill = name, skill
        record.preferences, record.coverage_template = preferences, template
        record.save()
        ScheduleEvent.objects.create(action='team_saved', detail={'team': record.key})
    except (KeyError, ValueError, TypeError, AttributeError): return error('Invalid team details or weekly template')
    return state_with_week(request, data.get('week') or date.today())

@csrf_exempt
def person(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    if data is None: return error('Invalid JSON')
    try:
        key = str(data['key']).strip()
        if not key or len(key) > 20: raise ValueError()
        name = str(data['name']).strip()
        target_team = Team.objects.get(key=data['team'])
        skills, preferences, availability = data.get('skills',[]), data.get('preferences',{}), data.get('availability',[])
        available_windows = data.get('available_windows',[])
        if not name or not isinstance(skills,list) or not isinstance(preferences,dict) or not isinstance(availability,list) or not isinstance(available_windows,list): raise ValueError()
        for period in [*availability, *available_windows]:
            if parsed_time(period['start']) >= parsed_time(period['end']): raise ValueError()
        record, _ = Employee.objects.get_or_create(key=key, defaults={'name': name, 'phone': '', 'classification': 'casual', 'team': target_team})
        record.name, record.phone, record.team = name, str(data.get('phone','')).strip(), target_team
        record.classification, record.skills = str(data.get('classification','casual')), skills
        record.preferences, record.availability, record.available_windows = preferences, availability, available_windows
        record.save()
        ScheduleEvent.objects.create(action='person_saved', detail={'person': record.key})
    except (KeyError, ValueError, TypeError, Team.DoesNotExist): return error('Invalid person details, skills or availability')
    return state_with_week(request, data.get('week') or date.today())

@csrf_exempt
def publish(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request) or {}
    try: monday, beginning, ending = week_bounds(data['week'])
    except (KeyError, ValueError, TypeError): return error('Valid week required')
    with transaction.atomic():
        draft = CoverageSlot.objects.filter(batch='draft', start__gte=beginning, start__lt=ending)
        if not draft.exists(): return error('Generate a draft for this week first')
        scheduled = list(Shift.objects.filter(batch='draft', start__lt=ending, end__gt=beginning).select_related('employee','team'))
        surrounding = list(Shift.objects.filter(batch='published', start__lt=ending+timedelta(days=2), end__gt=beginning-timedelta(days=2)).exclude(start__gte=beginning, start__lt=ending))
        blocked = {}
        def mark(item, reason):
            blocked.setdefault(item.id, set()).add(reason)
        for item in scheduled:
            if item.team.skill not in item.employee.skills: mark(item, 'Required team qualification is missing')
            if unavailable(item.employee, item): mark(item, 'Employee is unavailable during this shift')
            issue = placement_issue(item, [])
            if issue: mark(item, issue)
            for other in surrounding:
                if other.employee_id == item.employee_id:
                    issue = placement_issue(item, [other])
                    if issue: mark(item, issue + ' (adjacent published week)')
        for index, item in enumerate(scheduled):
            for other in scheduled[index+1:]:
                if other.employee_id != item.employee_id: continue
                # Single-shift issues were collected above; only mark both sides
                # when the combination is the blocker.
                if placement_issue(item, []) or placement_issue(other, []): continue
                issue = placement_issue(item, [other])
                if issue:
                    mark(item, issue)
                    mark(other, issue)
        callout_issues = callout_rest_issues(scheduled, beginning, ending)
        for item in scheduled:
            if item.id in callout_issues: mark(item, callout_issues[item.id])
        if blocked:
            details = [{'id': s.id, 'reason': '; '.join(sorted(blocked[s.id]))} for s in scheduled if s.id in blocked]
            return JsonResponse({'error': f'Cannot publish: {len(details)} shift(s) need attention. Highlighted in Schedule.', 'blocked_shifts': details}, status=409)
        CoverageSlot.objects.filter(batch='published', start__gte=beginning, start__lt=ending).delete()
        Shift.objects.filter(batch='published', start__gte=beginning, start__lt=ending).delete()
        draft.update(batch='published')
        Shift.objects.filter(batch='draft', start__gte=beginning, start__lt=ending).update(batch='published', published=True)
        revision = (Publication.objects.filter(week=monday).aggregate(last=Max('revision'))['last'] or 0)+1
        current = json.loads(state_with_week(request, monday).content)
        snapshot = {'week': monday.isoformat(), 'coverage': current['coverage'], 'shifts': current['shifts'], 'absences': current['absences'], 'callouts': current['callouts']}
        Publication.objects.create(week=monday, revision=revision, snapshot=snapshot)
        ScheduleEvent.objects.create(action='published', week=monday, detail={'revision': revision, 'shifts': len(scheduled)})
    return state_with_week(request,monday)

def oncall(request):
    try:
        now = parsed_time(request.GET['at']) if request.GET.get('at') else datetime.now(timezone.utc)
        key = request.GET.get('team')
        team_filter = {'team__key': key} if key and key != 'all' else {}
        upcoming = list(Shift.objects.filter(batch='published', end__gt=now, **team_filter).select_related('employee','team').order_by('start')[:8])
        near_shifts = list(Shift.objects.filter(batch='published', mode='on_call', end__gt=now, start__lt=now+timedelta(days=3), **team_filter).select_related('employee'))
        requirements = CoverageSlot.objects.filter(batch='published', mode='on_call', end__gt=now, start__lt=now+timedelta(days=3), **team_filter).select_related('team').order_by('start')
        gaps = []
        for slot in requirements:
            covered, _ = demand_coverage(slot, near_shifts)
            if covered < slot.required: gaps.append({'team': slot.team.key, 'start': slot.start.isoformat(), 'end': slot.end.isoformat(), 'missing': slot.required-covered})
        return JsonResponse({'at': now.isoformat(), 'people': [{'id':s.id, 'name':s.employee.name,'phone':s.employee.phone,'team':s.team.key,'start':s.start.isoformat(),'end':s.end.isoformat(),'current':s.start<=now, 'mode':s.mode} for s in upcoming[:8]], 'gaps': gaps[:8]})
    except ValueError: return error('Invalid time')


def history(request):
    try:
        week = week_bounds(request.GET['week'])[0]
        versions = Publication.objects.filter(week=week).order_by('-revision')
        selected = versions.get(revision=int(request.GET['revision'])) if request.GET.get('revision') else versions.first()
        events = list(ScheduleEvent.objects.filter(Q(week=week)|Q(week__isnull=True)).order_by('-created_at')[:30].values('action','actor','created_at','detail'))
        previous = versions.filter(revision=selected.revision-1).first() if selected else None
        def shift_key(item):
            return tuple(item.get(k) for k in ('employee','team','start','end','mode','break_minutes','location','role','notes'))
        current_set = {shift_key(x) for x in selected.snapshot.get('shifts',[])} if selected else set()
        prior_set = {shift_key(x) for x in previous.snapshot.get('shifts',[])} if previous else set()
        changes = {'added': len(current_set-prior_set), 'removed': len(prior_set-current_set)} if previous else None
        return JsonResponse({'changes': changes, 'week': week.isoformat(), 'versions': [{'revision': v.revision, 'created_at': v.created_at.isoformat(), 'actor': v.actor} for v in versions], 'snapshot': selected.snapshot if selected else None, 'events': events})
    except (ValueError, TypeError, Publication.DoesNotExist): return error('Invalid publication revision')

@csrf_exempt
def absence(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    if not isinstance(data, dict): return error('Invalid JSON')
    try:
        if data.get('delete'):
            item = Absence.objects.get(pk=data['id'])
            week = item.start.astimezone(PACIFIC).date()
            key = item.employee.key
            item.delete()
            ScheduleEvent.objects.create(action='absence_deleted', week=event_week(week), detail={'employee': key})
            return state_with_week(request, week)
        employee = Employee.objects.get(key=data['employee'])
        start, end = parsed_time(data['start']), parsed_time(data['end'])
        kind = data['kind']
        note = str(data.get('note', '')).strip()
        if start >= end or kind not in ('vacation','sick','other') or len(note)>250: raise ValueError()
        item = Absence.objects.create(employee=employee, start=start, end=end, kind=kind, note=note)
        week = start.astimezone(PACIFIC).date()
        ScheduleEvent.objects.create(action='absence_added', week=event_week(week), detail={'id': item.id, 'employee': employee.key, 'kind': kind})
        return state_with_week(request, week)
    except (KeyError, ValueError, TypeError, Absence.DoesNotExist, Employee.DoesNotExist): return error('Invalid time off details')

@csrf_exempt
def callout(request):
    if not admin_post(request): return error('Alpha admin required', 403)
    data = body(request)
    if not isinstance(data, dict): return error('Invalid JSON')
    try:
        if data.get('delete'):
            item = Callout.objects.get(pk=data['id'])
            week = item.start.astimezone(PACIFIC).date()
            item.delete()
            ScheduleEvent.objects.create(action='callout_deleted', week=event_week(week), detail={'id': data['id']})
            return state_with_week(request, week)
        standby = Shift.objects.select_related('employee').get(pk=data['shift'], batch='published', mode='on_call')
        start, end = parsed_time(data['start']), parsed_time(data['end'])
        note = str(data.get('note','')).strip()
        if start < standby.start or end > standby.end or start >= end or len(note)>250: raise ValueError()
        item = Callout.objects.create(standby_shift=standby, employee_key=standby.employee.key, employee_name=standby.employee.name, team_key=standby.team.key, start=start, end=end, note=note)
        week = start.astimezone(PACIFIC).date()
        ScheduleEvent.objects.create(action='callout_recorded', week=event_week(week), detail={'id': item.id, 'shift_id': standby.id, 'employee': standby.employee.key})
        return state_with_week(request, week)
    except (KeyError, ValueError, TypeError, Shift.DoesNotExist, Callout.DoesNotExist): return error('Invalid standby call-out details')

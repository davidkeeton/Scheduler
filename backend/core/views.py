import json
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Team, Employee, CoverageSlot, Assignment

PACIFIC = ZoneInfo("America/Vancouver")
EASTERN = ZoneInfo("America/Toronto")

def admin_required(request):
    return settings.ALPHA_AUTO_ADMIN

def response_error(message, status=400):
    return JsonResponse({"error": message}, status=status)

def payload(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None

def serialize_slot(slot):
    assigned = list(slot.assignments.all())
    return {"id": slot.id, "team": slot.team.key, "start": slot.start.isoformat(), "end": slot.end.isoformat(), "mode": slot.mode, "batch": slot.batch, "required": slot.required, "weight": float(slot.weight), "priority": slot.priority, "assignments": [{"id": a.id, "employee": a.employee.key, "published": a.published, "cross_team": a.cross_team} for a in assigned], "covered": len(assigned)}

def state(request):
    active_batch = "draft" if CoverageSlot.objects.filter(batch="draft").exists() else "published"
    slots = CoverageSlot.objects.filter(batch=active_batch).select_related("team").prefetch_related("assignments__employee").order_by("start", "team__key")
    return JsonResponse({"alpha_admin": settings.ALPHA_AUTO_ADMIN, "timezone": "America/Vancouver", "teams": list(Team.objects.values("key", "name", "skill")), "employees": [{"key": e.key, "name": e.name, "phone": e.phone, "team": e.team.key, "classification": e.classification, "skills": e.skills} for e in Employee.objects.select_related("team").order_by("key")], "slots": [serialize_slot(s) for s in slots]})

def utc(local_date, hour):
    return datetime.combine(local_date, time.min, PACIFIC).replace(hour=hour).astimezone(timezone.utc)

def add_slot(team, day, start_hour, end_hour, mode):
    start = utc(day, start_hour)
    end = utc(day + timedelta(days=1), 0) if end_hour == 24 else utc(day, end_hour)
    midpoint = start + (end - start) / 2
    eastern = midpoint.astimezone(EASTERN)
    if mode == "on_call":
        priority = 1 if day.weekday() >= 5 and 9 <= eastern.hour < 17 else (2 if day.weekday() >= 5 else 3)
        weight = {1: Decimal("1.00"), 2: Decimal("0.50"), 3: Decimal("0.25")}[priority]
    else:
        priority = 1
        weight = Decimal("0.90") if team.key == "team-1" else Decimal("0.80")
    return CoverageSlot.objects.create(team=team, start=start, end=end, mode=mode, required=1, weight=weight, priority=priority)

@csrf_exempt
def generate(request):
    if request.method != "POST" or not admin_required(request):
        return response_error("Alpha admin required", 403)
    data = payload(request)
    if data is None:
        return response_error("Invalid JSON")
    try:
        requested = date.fromisoformat(data.get("week", ""))
    except ValueError:
        return response_error("Supply a valid week date")
    monday = requested - timedelta(days=requested.weekday())
    with transaction.atomic():
        beginning, ending = utc(monday, 0), utc(monday + timedelta(days=7), 0)
        existing = CoverageSlot.objects.filter(batch="draft", start__gte=beginning, start__lt=ending).exists()
        if not existing:
            CoverageSlot.objects.filter(batch="draft").delete()
            published = list(CoverageSlot.objects.filter(batch="published", start__gte=beginning, start__lt=ending))
            if published:
                for old in published:
                    CoverageSlot.objects.create(team=old.team, start=old.start, end=old.end, mode=old.mode, required=old.required, weight=old.weight, priority=old.priority, batch="draft")
            else:
                t1, t2 = Team.objects.get(key="team-1"), Team.objects.get(key="team-2")
                for offset in range(7):
                    day = monday + timedelta(days=offset)
                    for a, b in [(0, 8), (8, 16), (16, 24)]:
                        add_slot(t2, day, a, b, "staffed")
                    if offset < 5:
                        for a, b, mode in [(0, 8, "on_call"), (8, 11, "on_call"), (11, 19, "staffed"), (19, 24, "on_call")]:
                            add_slot(t1, day, a, b, mode)
                    else:
                        for a, b in [(0, 8), (8, 16), (16, 24)]:
                            add_slot(t1, day, a, b, "on_call")
        Assignment.objects.filter(slot__batch="draft").delete()
        employees = list(Employee.objects.select_related("team"))
        hours = {e.id: 0 for e in employees}
        busy = {e.id: [] for e in employees}
        slots = list(CoverageSlot.objects.filter(batch="draft").select_related("team").order_by("-weight", "start", "team__key"))
        for slot in slots:
            for _ in range(slot.required):
                candidates = [e for e in employees if slot.team.skill in e.skills and all(slot.end <= a or slot.start >= b for a, b in busy[e.id])]
                candidates.sort(key=lambda e: (e.team_id != slot.team_id, hours[e.id], e.key))
                if not candidates:
                    break
                employee = candidates[0]
                Assignment.objects.create(slot=slot, employee=employee, cross_team=employee.team_id != slot.team_id)
                busy[employee.id].append((slot.start, slot.end))
                hours[employee.id] += (slot.end - slot.start).total_seconds() / 3600
    return state(request)

@csrf_exempt
def move(request):
    if request.method != "POST" or not admin_required(request):
        return response_error("Alpha admin required", 403)
    data = payload(request)
    if data is None:
        return response_error("Invalid JSON")
    try:
        assignment = Assignment.objects.select_related("slot__team").get(pk=data.get("assignment_id"))
        employee = Employee.objects.select_related("team").get(key=data.get("employee"))
    except (Assignment.DoesNotExist, Employee.DoesNotExist):
        return response_error("Assignment or employee not found", 404)
    if assignment.slot.batch != "draft":
        return response_error("Generate a new draft before changing a published assignment")
    if assignment.slot.team.skill not in employee.skills:
        return response_error("Employee lacks the required skill")
    if Assignment.objects.filter(employee=employee, slot__start__lt=assignment.slot.end, slot__end__gt=assignment.slot.start).exclude(pk=assignment.pk).exists():
        return response_error("Employee has an overlapping shift")
    assignment.employee = employee
    assignment.cross_team = employee.team_id != assignment.slot.team_id
    assignment.published = False
    assignment.save()
    return state(request)

@csrf_exempt
def publish(request):
    if request.method != "POST" or not admin_required(request):
        return response_error("Alpha admin required", 403)
    with transaction.atomic():
        draft = CoverageSlot.objects.filter(batch="draft")
        if not draft.exists():
            return response_error("Generate a draft first")
        beginning = draft.order_by("start").first().start
        ending = beginning + timedelta(days=8)
        CoverageSlot.objects.filter(batch="published", start__gte=beginning, start__lt=ending).delete()
        Assignment.objects.filter(slot__batch="draft").update(published=True)
        draft.update(batch="published")
    return state(request)

def oncall(request):
    try:
        at = datetime.fromisoformat(request.GET.get("at", "").replace("Z", "+00:00")) if request.GET.get("at") else datetime.now(timezone.utc)
        if at.tzinfo is None:
            return response_error("Time zone required")
    except ValueError:
        return response_error("Invalid time")
    assignments = Assignment.objects.select_related("employee", "slot__team").filter(published=True, slot__batch="published", slot__mode="on_call", slot__start__lte=at, slot__end__gt=at)
    return JsonResponse({"at": at.isoformat(), "people": [{"name": a.employee.name, "phone": a.employee.phone, "team": a.slot.team.name, "start": a.slot.start.isoformat(), "end": a.slot.end.isoformat()} for a in assignments]})

@csrf_exempt
def coverage(request):
    if request.method != "POST" or not admin_required(request):
        return response_error("Alpha admin required", 403)
    data = payload(request)
    if data is None:
        return response_error("Invalid JSON")
    try:
        slot = CoverageSlot.objects.get(pk=data.get("slot_id"))
        required = int(data.get("required"))
        weight = Decimal(str(data.get("weight")))
        if not 0 <= required <= 20 or not Decimal("0.01") <= weight <= Decimal("1.00"):
            raise ValueError
    except (CoverageSlot.DoesNotExist, ValueError, TypeError, ArithmeticError):
        return response_error("Use headcount 0-20 and weight 0.01-1.00")
    if slot.batch != "draft":
        return response_error("Generate a new draft before changing published coverage")
    slot.required = required
    slot.weight = weight
    slot.save(update_fields=["required", "weight"])
    return state(request)

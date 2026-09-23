"""Pilot BC scheduling checks. Payroll and actual call-outs need separate records."""
from collections import defaultdict
from datetime import timedelta

MIN_BETWEEN_SHIFTS_HOURS = 8
FULL_SHIFT_HOURS = 8  # Pilot definition for the stacking policy, not a BC legal limit.
MAX_STAFFED_HOURS = 12  # Pilot preference; 12 staffed + home standby remains possible.


def counted(slot, on_call_on_site=False):
    # BC ESA s.1(2): standby at a designated place other than home is work.
    # This pilot assumes home/mobile standby. Actual call-outs are not recorded.
    return slot.mode != "on_call" or on_call_on_site


def placement_issue(slot, existing, on_call_on_site=False):
    """Return a blocking issue for a proposed assignment, if any."""
    if slot.mode == 'staffed' and slot.end-slot.start > timedelta(hours=MAX_STAFFED_HOURS):
        return 'Staffed shift exceeds the pilot 12-hour shift preference'
    if any(slot.start < other.end and slot.end > other.start for other in existing):
        return "Employee has an overlapping assignment"
    for other in existing:
        adjacent = slot.start == other.end or other.start == slot.end
        full = all((s.end - s.start) >= timedelta(hours=FULL_SHIFT_HOURS) for s in (slot, other))
        if adjacent and full and slot.mode == other.mode:
            label = "standby periods" if slot.mode == "on_call" else "staffed shifts"
            return f"Pilot policy avoids stacking full {label} back-to-back"
    intervals = sorted(
        [(s.start, s.end) for s in [*existing, slot] if counted(s, on_call_on_site)],
        key=lambda pair: pair[0],
    )
    if not intervals:
        return None
    block_start, block_end = intervals[0]
    for start, end in intervals[1:]:
        gap = start - block_end
        if gap == timedelta(0):
            block_end = end
        else:
            if gap < timedelta(hours=MIN_BETWEEN_SHIFTS_HOURS):
                return "Fewer than 8 hours free between worked shifts (BC ESA s.36(2))"
            block_start, block_end = start, end
    return None


def schedule_advisories(assignments, week_start, week_end, on_call_on_site=False):
    """Show items that cannot be certified from scheduled coverage alone."""
    by_employee = defaultdict(list)
    for assignment in assignments:
        by_employee[assignment.employee_id].append(getattr(assignment, 'slot', assignment))
    advisories = []
    for employee_id, slots in by_employee.items():
        worked = sorted((s for s in slots if counted(s, on_call_on_site)), key=lambda s: s.start)
        # An employee is entitled to 32 consecutive hours free in any seven-day
        # period, or premium pay for work during that period (ESA s.36(1)).
        clipped = [(max(s.start, week_start), min(s.end, week_end)) for s in worked
                   if s.end > week_start and s.start < week_end]
        cursor = week_start
        gaps = []
        for start, end in clipped:
            if start > cursor:
                gaps.append(start - cursor)
            cursor = max(cursor, end)
        gaps.append(week_end - cursor)
        if clipped and max(gaps) < timedelta(hours=32):
            advisories.append({"employee_id": employee_id, "code": "BC_WEEKLY_REST_OR_PREMIUM",
                               "message": "No 32-hour work-free period is visible in this week; review premium pay and adjacent weeks (BC ESA s.36(1))."})
        if any(s.mode == "on_call" for s in slots) and not on_call_on_site:
            advisories.append({"employee_id": employee_id, "code": "CALL_OUT_UNRECORDED",
                               "message": "Home/mobile standby is assumed. Record actual call-outs and recheck 8-hour rest before the next worked shift."})
    return advisories

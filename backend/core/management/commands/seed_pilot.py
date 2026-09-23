import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Team, Employee, Assignment, Shift

def default_template(key):
    if key == "team-1":
        return ([{"days": [0, 1, 2, 3, 4], "start": a, "end": b, "mode": mode, "required": 1, "weight": weight}
                 for a, b, mode, weight in [(0, 8, "on_call", .25), (8, 11, "on_call", .25), (11, 19, "staffed", .9), (19, 24, "on_call", .25)]]
                + [{"days": [5, 6], "start": a, "end": b, "mode": "on_call", "required": 1, "weight": .5}
                   for a, b in [(0, 8), (8, 16), (16, 24)]])
    return [{"days": list(range(7)), "start": a, "end": b, "mode": "staffed", "required": 1, "weight": .8}
            for a, b in [(0, 8), (8, 16), (16, 24)]]

class Command(BaseCommand):
    def handle(self, *args, **options):
        data = json.loads((Path(__file__).resolve().parents[3] / "pilot-teams.json").read_text())
        for record in data["teams"]:
            Team.objects.get_or_create(key=record["id"], defaults={"name": record["name"], "skill": record["required_skill"], "coverage_template": default_template(record["id"]), "preferences": {"day_night": "consistent", "on_call_grouping": "paired", "weekend_continuity": True}})
        for record in data["employees"]:
            Employee.objects.get_or_create(key=record["id"], defaults={"name": record["name"], "phone": record["phone"], "team": Team.objects.get(key=record["team_id"]), "classification": record["classification"], "skills": record["skills"]})
        # Preserve schedules from the first alpha when upgrading an existing volume.
        if not Shift.objects.exists():
            for assignment in Assignment.objects.select_related("slot", "employee", "slot__team"):
                slot = assignment.slot
                Shift.objects.get_or_create(employee=assignment.employee, team=slot.team, start=slot.start, end=slot.end, mode=slot.mode, batch=slot.batch, defaults={"published": assignment.published})
        admin, created = get_user_model().objects.get_or_create(username="alpha-master", defaults={"is_staff": True, "is_superuser": True})
        if created:
            admin.set_unusable_password()
            admin.save(update_fields=["password"])
        self.stdout.write("Pilot teams seeded")

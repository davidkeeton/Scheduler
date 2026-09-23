import json
from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Team, Employee

class Command(BaseCommand):
    def handle(self, *args, **options):
        data = json.loads((Path(__file__).resolve().parents[3] / "pilot-teams.json").read_text())
        for record in data["teams"]:
            Team.objects.update_or_create(key=record["id"], defaults={"name": record["name"], "skill": record["required_skill"]})
        for record in data["employees"]:
            Employee.objects.update_or_create(key=record["id"], defaults={"name": record["name"], "phone": record["phone"], "team": Team.objects.get(key=record["team_id"]), "classification": record["classification"], "skills": record["skills"]})
        admin, created = get_user_model().objects.get_or_create(username="alpha-master", defaults={"is_staff": True, "is_superuser": True})
        if created:
            admin.set_unusable_password()
            admin.save(update_fields=["password"])
        self.stdout.write("Pilot teams seeded")

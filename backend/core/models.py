from django.db import models

class Team(models.Model):
    key = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=100)
    skill = models.CharField(max_length=80)
    coverage_template = models.JSONField(default=list)
    preferences = models.JSONField(default=dict)

class Employee(models.Model):
    key = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    team = models.ForeignKey(Team, on_delete=models.PROTECT)
    classification = models.CharField(max_length=30)
    skills = models.JSONField(default=list)
    preferences = models.JSONField(default=dict)
    availability = models.JSONField(default=list)
    available_windows = models.JSONField(default=list)

class CoverageSlot(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    start = models.DateTimeField()
    end = models.DateTimeField()
    mode = models.CharField(max_length=20)
    required = models.PositiveSmallIntegerField(default=1)
    weight = models.DecimalField(max_digits=3, decimal_places=2, default=1)
    priority = models.PositiveSmallIntegerField(default=1)
    batch = models.CharField(max_length=20, default="draft")
    required_skill = models.CharField(max_length=80, blank=True, default="")

class Assignment(models.Model):
    slot = models.ForeignKey(CoverageSlot, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    published = models.BooleanField(default=False)
    cross_team = models.BooleanField(default=False)

class Shift(models.Model):
    """A person's actual assignment, independent of coverage demand windows."""
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name="shifts")
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="shifts")
    start = models.DateTimeField()
    end = models.DateTimeField()
    mode = models.CharField(max_length=20)
    batch = models.CharField(max_length=20, default="draft")
    published = models.BooleanField(default=False)
    break_minutes = models.PositiveSmallIntegerField(default=0)
    location = models.CharField(max_length=100, blank=True, default='')
    role = models.CharField(max_length=80, blank=True, default='')
    notes = models.CharField(max_length=500, blank=True, default='')

class Publication(models.Model):
    """Immutable copy of a week each time it is published."""
    week = models.DateField(db_index=True)
    revision = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=80, default='Alpha administrator')
    snapshot = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['week', 'revision'], name='unique_week_revision')]
        ordering = ['-week', '-revision']

class ScheduleEvent(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=80, default='Alpha administrator')
    action = models.CharField(max_length=60)
    week = models.DateField(null=True, blank=True)
    detail = models.JSONField(default=dict)

class Absence(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    start = models.DateTimeField()
    end = models.DateTimeField()
    kind = models.CharField(max_length=20)
    note = models.CharField(max_length=250, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

class Callout(models.Model):
    standby_shift = models.ForeignKey(Shift, on_delete=models.SET_NULL, null=True, blank=True)
    employee_key = models.CharField(max_length=20, default="")
    employee_name = models.CharField(max_length=100, default="")
    team_key = models.CharField(max_length=40, default="")
    start = models.DateTimeField()
    end = models.DateTimeField()
    note = models.CharField(max_length=250, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

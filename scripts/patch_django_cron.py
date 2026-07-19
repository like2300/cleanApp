#!/usr/bin/env python3
"""
Patch de compatibilité django-cron pour Django 5.1+.

django-cron déclare ``index_together`` dans la Meta de son modèle ``CronJobLog``,
attribut supprimé en Django 5.1.

Ce script écrase le fichier ``django_cron/models.py`` installé avec une version
100% compatible et valide utilisant ``indexes = [...]`` au lieu de ``index_together``.
"""

import importlib.util
import pathlib

CORRECT_MODELS_CONTENT = """from django.db import models


class CronJobLog(models.Model):
    \"\"\"
    Keeps track of the cron jobs that ran etc. and any error
    messages if they failed.
    \"\"\"

    code = models.CharField(max_length=64, db_index=True)
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField(db_index=True)
    is_success = models.BooleanField(default=False)
    message = models.TextField(default='', blank=True)  # TODO: db_index=True

    # This field is used to mark jobs executed in exact time.
    # Jobs that run every X minutes, have this field empty.
    ran_at_time = models.TimeField(null=True, blank=True, db_index=True, editable=False)

    def __unicode__(self):
        return '%s (%s)' % (self.code, 'Success' if self.is_success else 'Fail')

    def __str__(self):
        return "%s (%s)" % (self.code, "Success" if self.is_success else "Fail")

    class Meta:
        indexes = [
            models.Index(fields=['code', 'is_success', 'ran_at_time']),
            models.Index(fields=['code', 'start_time', 'ran_at_time']),
            models.Index(fields=['code', 'start_time']),
        ]
        app_label = 'django_cron'


class CronJobLock(models.Model):
    job_name = models.CharField(max_length=200, unique=True)
    locked = models.BooleanField(default=False)
"""


def main():
    spec = importlib.util.find_spec("django_cron")
    if not spec or not spec.origin:
        print("django_cron non trouvé, rien à patcher.")
        return

    p = pathlib.Path(spec.origin).parent / "models.py"
    if not p.exists():
        print(f"{p} introuvable, rien à patcher.")
        return

    p.write_text(CORRECT_MODELS_CONTENT, encoding="utf-8")
    print("django_cron/models.py a ete ecrase et mis a jour pour Django 5.1+ [OK]")


if __name__ == "__main__":
    main()

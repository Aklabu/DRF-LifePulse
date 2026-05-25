from django.core.management.base import BaseCommand
from apps.monitoring.tasks import create_daily_monitoring_logs


class Command(BaseCommand):
    help = 'Manually trigger daily monitoring log creation for today (dev use).'

    def handle(self, *args, **options):
        count = create_daily_monitoring_logs()
        self.stdout.write(self.style.SUCCESS(f'Created {count} monitoring log(s) for today.'))

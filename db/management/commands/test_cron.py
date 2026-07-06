from datetime import datetime
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        with open("/tmp/test_cron.log", "a") as f:
            f.write(f"Executed at {datetime.now()}\n")
            f.write("Cron executed successfully\n")
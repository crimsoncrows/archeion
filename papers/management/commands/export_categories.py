import csv

from django.core.management.base import BaseCommand

from papers.models import PaperCategory


class Command(BaseCommand):
    help = "Export each paper's system-assigned category to system_categories.csv."

    def handle(self, *args, **opts):
        rows = PaperCategory.objects.select_related("paper", "category")
        with open("system_categories.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["title", "system_category"])
            for pc in rows.order_by("paper__title"):
                writer.writerow([pc.paper.title, pc.category.category_name])
        self.stdout.write(self.style.SUCCESS(f"Exported {rows.count()} rows.")) 
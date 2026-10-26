from django.core.management.base import BaseCommand

from papers.classification import assign_category
from similarity.models import Embedding


class Command(BaseCommand):
    help = "Assign each paper to its closest category using BGE-M3 embeddings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--review-margin", type=float, default=0.02,
            help="Flag papers whose top two categories are this close.",
        )

    def handle(self, *args, **opts):
        margin_limit = opts["review_margin"]
        flagged = 0
        for emb in Embedding.objects.select_related("paper"):
            name, score, margin = assign_category(emb.paper, emb)
            flag = "  <-- REVIEW" if margin < margin_limit else ""
            if flag:
                flagged += 1
            self.stdout.write(
                f"{emb.paper.title[:60]:60} | {name} | {score:.3f} | +{margin:.3f}{flag}"
            )
        self.stdout.write(self.style.SUCCESS(f"Done. {flagged} paper(s) flagged for manual review."))
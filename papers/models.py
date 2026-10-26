from django.db import models
from django.conf import settings 
from django.core.exceptions import ValidationError
import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def validate_pdf(f):
    # Already-stored files (editing without re-uploading) are skipped.
    if getattr(f, '_committed', False):
        return
    if not f.name.lower().endswith('.pdf'):
        raise ValidationError("Only PDF files are allowed.")
    if f.size > 10 * 1024 * 1024:
        raise ValidationError("File too large (10 MB max).")
    f.seek(0)
    if f.read(5) != b'%PDF-':
        raise ValidationError("File is not a valid PDF.")
    f.seek(0)

class Category(models.Model):
    category_id = models.AutoField(primary_key=True)
    category_name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.category_name


class RepositoryPaperManager(models.Manager):
    """Default manager: hides students' similarity-check submissions,
    so Browse, Trends, admin and counts only ever see repository papers."""
    def get_queryset(self):
        return super().get_queryset().exclude(type='submission')


class ResearchPaper(models.Model):
    TYPE_CHOICES = [
        ('thesis', 'Thesis'),
        ('capstone', 'Capstone'),
        ('submission', 'Similarity check submission'),  # a student's check, never shown in the repository
    ]

    paper_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255)
    abstract = models.TextField()
    authors = models.CharField(max_length=255)  # consider a separate Author model later if you need per-author queries
    year = models.PositiveIntegerField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    program = models.CharField(max_length=100)
    file_path = models.FileField(upload_to='research_papers/', validators=[validate_pdf], max_length=500, blank=True)  # blank for submissions: uploads are never stored
    upload_date = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='uploaded_papers',
        db_constraint=False,   # added
    )
    categories = models.ManyToManyField(Category, through='PaperCategory', related_name='papers')

    objects = RepositoryPaperManager()   # default: repository papers only
    all_objects = models.Manager()       # includes submissions; used only when saving checks

    def __str__(self):
        return self.title


class PaperCategory(models.Model):
    paper = models.ForeignKey(ResearchPaper, on_delete=models.CASCADE, db_constraint=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, db_constraint=False)

    class Meta:
        unique_together = ('paper', 'category')


@receiver(post_delete, sender=ResearchPaper)
def delete_paper_file(sender, instance, **kwargs):
    file_field = instance.file_path
    if not file_field:
        return

    def _delete():
        try:
            file_field.delete(save=False)
        except Exception:
            logger.exception("Could not delete file %s", file_field.name)

    transaction.on_commit(_delete)
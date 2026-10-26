from django.db import models
from papers.models import ResearchPaper
from django.conf import settings


class Feedback(models.Model):
    feedback_id = models.AutoField(primary_key=True)
    rating = models.IntegerField()
    message = models.TextField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )

    def __str__(self):
        return f"Feedback #{self.feedback_id} by {self.user} (rating: {self.rating})"

 
class Embedding(models.Model):
    embedding_id = models.AutoField(primary_key=True)
    paper = models.OneToOneField(
        ResearchPaper,
        on_delete=models.CASCADE,
        related_name='embedding'
    )  # 1:1 — each paper has exactly one embedding record
    vector_data = models.BinaryField()  # stores the actual embedding vector (serialized)
 
    def __str__(self):
        return f"Embedding for {self.paper.title}"
 
 
class SimilarityResult(models.Model):
    similarity_id = models.AutoField(primary_key=True)
    input_paper = models.ForeignKey(
        ResearchPaper,
        on_delete=models.CASCADE,
        related_name='similarity_as_input'
    )
    compared_paper = models.ForeignKey(
        ResearchPaper,
        on_delete=models.CASCADE,
        related_name='similarity_as_compared'
    )
    similarity_score = models.FloatField()
    rank_order = models.PositiveIntegerField()
 
    def __str__(self):
        return f"{self.input_paper.title} vs {self.compared_paper.title} ({self.similarity_score:.2f})"
 
 
class FFM(models.Model):
    feature_id = models.AutoField(primary_key=True)
    feature_name = models.CharField(max_length=150)
    domain = models.CharField(max_length=100)  # e.g. groups related features together
 
    def __str__(self):
        return self.feature_name
 
 
class FFMResult(models.Model):
    ffm_id = models.AutoField(primary_key=True)
    similarity = models.ForeignKey(
        SimilarityResult,
        on_delete=models.CASCADE,
        related_name='ffm_results'
    )
    generated_at = models.DateTimeField(auto_now_add=True)
 
    def __str__(self):
        return f"FFM Result #{self.ffm_id} for similarity #{self.similarity.similarity_id}"
 
 
class FFMEntry(models.Model):
    ffm_entry_id = models.AutoField(primary_key=True)
    ffm_result = models.ForeignKey(
        FFMResult,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    paper = models.ForeignKey(
        ResearchPaper,
        on_delete=models.CASCADE,
        related_name='ffm_entries'
    )
    feature = models.ForeignKey(
        FFM,
        on_delete=models.CASCADE,
        related_name='entries'
    )
    is_present = models.BooleanField(default=False)
    analysis = models.TextField(blank=True, null=True)  # Claude's explanation of why the feature was marked present/absent
 
    class Meta:
        unique_together = ('ffm_result', 'paper', 'feature')
 
    def __str__(self):
        return f"{self.feature.feature_name} - {self.paper.title} ({'Yes' if self.is_present else 'No'})"
 

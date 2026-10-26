from django.contrib import admin
from .models import Feedback,Embedding, SimilarityResult, FFM, FFMResult, FFMEntry

admin.site.register(Embedding)
admin.site.register(Feedback)
admin.site.register(SimilarityResult)
admin.site.register(FFM)
admin.site.register(FFMResult)
admin.site.register(FFMEntry)
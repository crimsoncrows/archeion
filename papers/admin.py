from django.contrib import admin
from .models import ResearchPaper, Category, PaperCategory

class PaperCategoryInline(admin.TabularInline):
    model = PaperCategory
    extra = 1

class ResearchPaperAdmin(admin.ModelAdmin):
    inlines = [PaperCategoryInline]

admin.site.register(ResearchPaper, ResearchPaperAdmin)
admin.site.register(Category)
admin.site.register(PaperCategory)
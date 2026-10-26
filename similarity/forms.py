from pathlib import Path

from django import forms
from .models import Feedback

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # matches the 10 MB upload cap
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}  # FR6


class FeedbackForm(forms.ModelForm):
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        error_messages={'required': 'Please select a rating.'},
        widget=forms.HiddenInput(attrs={'id': 'id_rating'})
    )
    message = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'form-control input-sim-text',
            'placeholder': 'Write your feedback here. (OPTIONAL)',
            'rows': 4,
        })
    )

    class Meta:
        model = Feedback
        fields = ['rating', 'message']

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is None or not (1 <= rating <= 5):
            raise forms.ValidationError('Please select a rating between 1 and 5.')
        return rating


class SimilarityForm(forms.Form):
    document_file = forms.FileField(required=False)
    text_input = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control input-sim-text',
            'placeholder': 'Paste your title, abstract, or full manuscript here.',
            'rows': 8,
        })
    )

    def clean_document_file(self):
        f = self.cleaned_data.get('document_file')
        if not f:
            return f
        if f.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError('File must be 10 MB or smaller.')

        ext = Path(f.name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise forms.ValidationError('Only PDF, DOCX, or TXT files are accepted.')

        # Check the real content, not just the extension
        head = f.read(4096)
        f.seek(0)
        if ext == '.pdf' and not head.startswith(b'%PDF-'):
            raise forms.ValidationError('This file is not a valid PDF.')
        if ext == '.docx' and not head.startswith(b'PK\x03\x04'):
            raise forms.ValidationError('This file is not a valid DOCX.')
        if ext == '.txt' and b'\x00' in head:
            raise forms.ValidationError('This file is not a plain text file.')
        return f

    def clean(self):
        data = super().clean()
        if 'document_file' in self.errors:
            return data  # the file was rejected; its own error already explains why
        if not data.get('document_file') and not (data.get('text_input') or '').strip():
            raise forms.ValidationError('Upload a file or paste your text.')  # FT-12
        return data
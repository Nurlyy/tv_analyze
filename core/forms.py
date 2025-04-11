from django import forms
from .models import MediaFile

class MediaFileForm(forms.ModelForm):
    class Meta:
        model = MediaFile
        fields = ['file', 'file_url', 'language']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://example.com/video.mp4'}),
            'language': forms.Select(attrs={'class': 'form-control'})
        }
    
    def clean(self):
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        file_url = cleaned_data.get('file_url')
        
        # Проверяем, что хотя бы одно из полей file или file_url заполнено
        if not file and not file_url:
            raise forms.ValidationError("Необходимо загрузить файл или указать URL")
        
        return cleaned_data
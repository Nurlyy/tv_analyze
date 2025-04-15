from django import forms
from .models import MediaFile, Channel, TVShow, Episode

class ChannelForm(forms.ModelForm):
    class Meta:
        model = Channel
        fields = ['name', 'description', 'logo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'logo': forms.FileInput(attrs={'class': 'form-control'})
        }

class TVShowForm(forms.ModelForm):
    class Meta:
        model = TVShow
        fields = ['name', 'channel', 'category', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'channel': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        }

class EpisodeForm(forms.ModelForm):
    class Meta:
        model = Episode
        fields = ['show', 'air_date', 'title']
        widgets = {
            'show': forms.Select(attrs={'class': 'form-select'}),
            'air_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'title': forms.TextInput(attrs={'class': 'form-control'})
        }

class MediaFileForm(forms.ModelForm):
    class Meta:
        model = MediaFile
        fields = ['file', 'file_url', 'language', 'episode']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'file_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.youtube.com/watch?v=...'}),
            'language': forms.Select(attrs={'class': 'form-select'}),
            'episode': forms.Select(attrs={'class': 'form-select'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Делаем поле episode необязательным визуально
        self.fields['episode'].required = False
        # Добавляем класс select2 для улучшения работы с выпадающими списками
        if 'episode' in self.fields:
            self.fields['episode'].widget.attrs.update({'class': 'form-select select2'})


class TVAnalysisForm(forms.Form):
    """Форма для выбора телеканала, передачи и даты для анализа"""
    channel = forms.ModelChoiceField(
        queryset=Channel.objects.all().order_by('name'),
        empty_label="Выберите телеканал",
        widget=forms.Select(attrs={'class': 'form-select select2', 'id': 'id_channel'})
    )
    
    show = forms.ModelChoiceField(
        queryset=TVShow.objects.none(),
        empty_label="Сначала выберите телеканал",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select select2', 'id': 'id_show'})
    )
    
    episode = forms.ModelChoiceField(
        queryset=Episode.objects.none(),
        empty_label="Сначала выберите передачу",
        required=False,
        widget=forms.Select(attrs={'class': 'form-select select2', 'id': 'id_episode'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Если выбран телеканал, фильтруем передачи
        if 'channel' in self.data:
            try:
                channel_id = int(self.data.get('channel'))
                self.fields['show'].queryset = TVShow.objects.filter(
                    channel_id=channel_id).order_by('name')
                self.fields['show'].empty_label = "Выберите передачу"
            except (ValueError, TypeError):
                pass  # неверный ID телеканала, используем пустой queryset
                
        # Если выбрана передача, фильтруем выпуски
        if 'show' in self.data:
            try:
                show_id = int(self.data.get('show'))
                self.fields['episode'].queryset = Episode.objects.filter(
                    show_id=show_id).order_by('-air_date')
                self.fields['episode'].empty_label = "Выберите выпуск"
            except (ValueError, TypeError):
                pass  # неверный ID передачи, используем пустой queryset
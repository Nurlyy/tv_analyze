from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.db.models import Q

from .models import MediaFile, Channel, TVShow, Episode, AnalysisMetrics
from .tasks import process_media
from .forms import MediaFileForm, ChannelForm, TVShowForm, EpisodeForm, TVAnalysisForm

# Главная страница
class IndexView(View):
    def get(self, request):
        form = TVAnalysisForm()
        recent_files = MediaFile.objects.filter(result__isnull=False).order_by('-created_at')[:5]
        
        return render(request, 'index.html', {
            'form': form,
            'recent_files': recent_files
        })

# AJAX для получения передач по телеканалу
class GetShowsView(View):
    def get(self, request):
        channel_id = request.GET.get('channel_id')
        if not channel_id:
            return JsonResponse({'shows': []})
        
        shows = list(TVShow.objects.filter(channel_id=channel_id).values('id', 'name'))
        return JsonResponse({'shows': shows})

# AJAX для получения выпусков по передаче
class GetEpisodesView(View):
    def get(self, request):
        show_id = request.GET.get('show_id')
        if not show_id:
            return JsonResponse({'episodes': []})
        
        episodes = list(Episode.objects.filter(show_id=show_id).order_by('-air_date').values('id', 'air_date', 'title'))
        
        # Преобразуем даты в строки
        for episode in episodes:
            episode['air_date'] = episode['air_date'].strftime('%d.%m.%Y')
            display_title = episode['title'] if episode['title'] else f"Выпуск от {episode['air_date']}"
            episode['display_title'] = display_title
        
        return JsonResponse({'episodes': episodes})

# Представление для анализа телепередачи
class TVShowAnalysisView(View):
    def get(self, request, episode_id=None):
        # Если указан ID выпуска, выбираем его
        if episode_id:
            episode = get_object_or_404(Episode, id=episode_id)
            # Ищем медиафайл для этого выпуска
            media_files = MediaFile.objects.filter(episode=episode)
            
            if media_files.exists():
                # Берем первый файл с результатом или первый в списке
                media_file = media_files.filter(result__isnull=False).first() or media_files.first()
                
                # Если файл найден, но нет результатов - запускаем обработку
                if media_file and media_file.result is None:
                    process_media.delay(media_file.id)
                    messages.info(request, 'Запущена обработка файла. Пожалуйста, подождите несколько минут.')
                
                # Получаем метрики для файла если они есть
                try:
                    metrics = AnalysisMetrics.objects.get(media_file=media_file)
                except AnalysisMetrics.DoesNotExist:
                    metrics = None
                
                return render(request, 'episode_analysis.html', {
                    'episode': episode,
                    'media_file': media_file,
                    'metrics': metrics
                })
            else:
                # Если файла нет, предлагаем его загрузить
                return render(request, 'episode_no_file.html', {
                    'episode': episode
                })
        
        # Если ID не указан, показываем форму выбора
        form = TVAnalysisForm(request.GET or None)
        
        if form.is_valid():
            episode = form.cleaned_data['episode']
            if episode:
                return redirect('episode_analysis', episode_id=episode.id)
            else:
                messages.warning(request, 'Пожалуйста, выберите выпуск для анализа')
        
        return render(request, 'tv_analysis_form.html', {
            'form': form
        })

    def post(self, request, episode_id):
        episode = get_object_or_404(Episode, id=episode_id)
        
        # Проверяем наличие файла или URL
        uploaded_file = request.FILES.get("media")
        file_url = request.POST.get("file_url")
        language = request.POST.get("language", "auto")
        
        if not uploaded_file and not file_url:
            messages.error(request, 'Необходимо загрузить файл или указать URL')
            return redirect('episode_analysis', episode_id=episode_id)
            
        # Создаем экземпляр модели с соответствующими параметрами
        instance = MediaFile(language=language, episode=episode)
        
        if uploaded_file:
            instance.file = uploaded_file
        elif file_url:
            instance.file_url = file_url
        
        instance.save()
        
        # Запускаем задачу Celery
        task = process_media.delay(instance.id)
        
        messages.success(request, 'Файл успешно загружен и отправлен на обработку')
        return redirect('episode_analysis', episode_id=episode_id)


# List view - shows all items with limited info
class MediaFileListView(ListView):
    model = MediaFile
    template_name = 'mediafile_list.html'
    context_object_name = 'files'
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        search_query = self.request.GET.get('search', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(file__icontains=search_query) | 
                Q(file_url__icontains=search_query) |
                Q(episode__title__icontains=search_query) |
                Q(episode__show__name__icontains=search_query) |
                Q(episode__show__channel__name__icontains=search_query)
            )
        
        return queryset

# Detail view - shows all info for one item
class MediaFileDetailView(DetailView):
    model = MediaFile
    template_name = 'mediafile_detail.html'
    context_object_name = 'file'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Добавляем метрики, если они есть
        try:
            context['metrics'] = AnalysisMetrics.objects.get(media_file=self.object)
        except AnalysisMetrics.DoesNotExist:
            context['metrics'] = None
        return context

# Create view - with AJAX for loading animation
class MediaFileCreateView(View):
    def get(self, request):
        form = MediaFileForm()
        return render(request, 'mediafile_create.html', {'form': form})
    
    def post(self, request):
        # Проверяем наличие файла или URL
        uploaded_file = request.FILES.get("media")
        file_url = request.POST.get("file_url")
        language = request.POST.get("language", "auto")
        episode_id = request.POST.get("episode")
        
        if not uploaded_file and not file_url:
            return JsonResponse({'status': 'error', 'message': 'Необходимо загрузить файл или указать URL'}, status=400)
            
        # Создаем экземпляр модели с соответствующими параметрами
        instance = MediaFile(language=language)
        
        if uploaded_file:
            instance.file = uploaded_file
        elif file_url:
            instance.file_url = file_url
        
        # Если указан эпизод, связываем с ним
        if episode_id:
            try:
                episode = Episode.objects.get(id=episode_id)
                instance.episode = episode
            except Episode.DoesNotExist:
                pass
        
        instance.save()
        
        # Запускаем задачу Celery
        task = process_media.delay(instance.id)
        
        # Возвращаем JSON с ID задачи и ID файла для опроса
        return JsonResponse({
            'status': 'success',
            'file_id': instance.id,
            'task_id': task.id
        })

# Update view
class MediaFileUpdateView(UpdateView):
    model = MediaFile
    form_class = MediaFileForm
    template_name = 'mediafile_update.html'
    success_url = reverse_lazy('mediafile_list')

# Delete view
class MediaFileDeleteView(DeleteView):
    model = MediaFile
    template_name = 'mediafile_confirm_delete.html'
    success_url = reverse_lazy('mediafile_list')

# API endpoint to check if processing is complete
class CheckProcessingStatusView(View):
    def get(self, request, file_id):
        try:
            media_file = MediaFile.objects.get(pk=file_id)
            # If result is not None, processing is complete
            if media_file.result is not None:
                return JsonResponse({
                    'status': 'complete',
                    'redirect_url': reverse_lazy('mediafile_detail', kwargs={'pk': file_id})
                })
            else:
                return JsonResponse({'status': 'processing'})
        except MediaFile.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'File not found'}, status=404)

# Администрирование данных

# Телеканалы
class ChannelListView(ListView):
    model = Channel
    template_name = 'admin/channel_list.html'
    context_object_name = 'channels'

class ChannelCreateView(CreateView):
    model = Channel
    form_class = ChannelForm
    template_name = 'admin/channel_form.html'
    success_url = reverse_lazy('channel_list')

class ChannelUpdateView(UpdateView):
    model = Channel
    form_class = ChannelForm
    template_name = 'admin/channel_form.html'
    success_url = reverse_lazy('channel_list')

class ChannelDeleteView(DeleteView):
    model = Channel
    template_name = 'admin/channel_confirm_delete.html'
    success_url = reverse_lazy('channel_list')

# Телепередачи
class TVShowListView(ListView):
    model = TVShow
    template_name = 'admin/tvshow_list.html'
    context_object_name = 'shows'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        channel_id = self.request.GET.get('channel')
        
        if channel_id:
            queryset = queryset.filter(channel_id=channel_id)
            
        return queryset.select_related('channel')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['channels'] = Channel.objects.all()
        context['selected_channel'] = self.request.GET.get('channel')
        return context

class TVShowCreateView(CreateView):
    model = TVShow
    form_class = TVShowForm
    template_name = 'admin/tvshow_form.html'
    success_url = reverse_lazy('tvshow_list')

class TVShowUpdateView(UpdateView):
    model = TVShow
    form_class = TVShowForm
    template_name = 'admin/tvshow_form.html'
    success_url = reverse_lazy('tvshow_list')

class TVShowDeleteView(DeleteView):
    model = TVShow
    template_name = 'admin/tvshow_confirm_delete.html'
    success_url = reverse_lazy('tvshow_list')

# Выпуски
class EpisodeListView(ListView):
    model = Episode
    template_name = 'admin/episode_list.html'
    context_object_name = 'episodes'
    
    def get_queryset(self):
        queryset = super().get_queryset()
        show_id = self.request.GET.get('show')
        
        if show_id:
            queryset = queryset.filter(show_id=show_id)
            
        return queryset.select_related('show', 'show__channel').order_by('-air_date')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['shows'] = TVShow.objects.all().order_by('name')
        context['selected_show'] = self.request.GET.get('show')
        return context

class EpisodeCreateView(CreateView):
    model = Episode
    form_class = EpisodeForm
    template_name = 'admin/episode_form.html'
    success_url = reverse_lazy('episode_list')

class EpisodeUpdateView(UpdateView):
    model = Episode
    form_class = EpisodeForm
    template_name = 'admin/episode_form.html'
    success_url = reverse_lazy('episode_list')

class EpisodeDeleteView(DeleteView):
    model = Episode
    template_name = 'admin/episode_confirm_delete.html'
    success_url = reverse_lazy('episode_list')
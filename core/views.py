from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import MediaFile
from .tasks import process_media
from .forms import MediaFileForm

# List view - shows all items with limited info
class MediaFileListView(ListView):
    model = MediaFile
    template_name = 'mediafile_list.html'
    context_object_name = 'files'
    ordering = ['-created_at']

# Detail view - shows all info for one item
class MediaFileDetailView(DetailView):
    model = MediaFile
    template_name = 'mediafile_detail.html'
    context_object_name = 'file'

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
        
        if not uploaded_file and not file_url:
            return JsonResponse({'status': 'error', 'message': 'Необходимо загрузить файл или указать URL'}, status=400)
            
        # Создаем экземпляр модели с соответствующими параметрами
        instance = MediaFile(language=language)
        
        if uploaded_file:
            instance.file = uploaded_file
        elif file_url:
            instance.file_url = file_url
        
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
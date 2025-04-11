from django.contrib import admin
from django.urls import path
from core import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.MediaFileListView.as_view(), name='mediafile_list'),
    path('files/<int:pk>/', views.MediaFileDetailView.as_view(), name='mediafile_detail'),
    path('files/create/', views.MediaFileCreateView.as_view(), name='mediafile_create'),
    path('files/<int:pk>/update/', views.MediaFileUpdateView.as_view(), name='mediafile_update'),
    path('files/<int:pk>/delete/', views.MediaFileDeleteView.as_view(), name='mediafile_delete'),
    path('files/<int:file_id>/status/', views.CheckProcessingStatusView.as_view(), name='check_processing_status'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
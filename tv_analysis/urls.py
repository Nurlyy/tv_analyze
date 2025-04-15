from django.urls import path
from core import views

urlpatterns = [
    # Главная страница и анализ телепередач
    path('', views.IndexView.as_view(), name='index'),
    path('analyze/', views.TVShowAnalysisView.as_view(), name='tv_analysis'),
    path('analyze/episode/<int:episode_id>/', views.TVShowAnalysisView.as_view(), name='episode_analysis'),
    
    # AJAX эндпоинты для динамической загрузки данных
    path('ajax/get-shows/', views.GetShowsView.as_view(), name='get_shows'),
    path('ajax/get-episodes/', views.GetEpisodesView.as_view(), name='get_episodes'),
    
    # Управление медиафайлами
    path('files/', views.MediaFileListView.as_view(), name='mediafile_list'),
    path('files/<int:pk>/', views.MediaFileDetailView.as_view(), name='mediafile_detail'),
    path('files/create/', views.MediaFileCreateView.as_view(), name='mediafile_create'),
    path('files/<int:pk>/update/', views.MediaFileUpdateView.as_view(), name='mediafile_update'),
    path('files/<int:pk>/delete/', views.MediaFileDeleteView.as_view(), name='mediafile_delete'),
    path('files/<int:file_id>/status/', views.CheckProcessingStatusView.as_view(), name='check_processing_status'),
    
    # Административные маршруты для управления данными
    # Телеканалы
    path('admin/channels/', views.ChannelListView.as_view(), name='channel_list'),
    path('admin/channels/create/', views.ChannelCreateView.as_view(), name='channel_create'),
    path('admin/channels/<int:pk>/update/', views.ChannelUpdateView.as_view(), name='channel_update'),
    path('admin/channels/<int:pk>/delete/', views.ChannelDeleteView.as_view(), name='channel_delete'),
    
    # Телепередачи
    path('admin/shows/', views.TVShowListView.as_view(), name='tvshow_list'),
    path('admin/shows/create/', views.TVShowCreateView.as_view(), name='tvshow_create'),
    path('admin/shows/<int:pk>/update/', views.TVShowUpdateView.as_view(), name='tvshow_update'),
    path('admin/shows/<int:pk>/delete/', views.TVShowDeleteView.as_view(), name='tvshow_delete'),
    
    # Выпуски
    path('admin/episodes/', views.EpisodeListView.as_view(), name='episode_list'),
    path('admin/episodes/create/', views.EpisodeCreateView.as_view(), name='episode_create'),
    path('admin/episodes/<int:pk>/update/', views.EpisodeUpdateView.as_view(), name='episode_update'),
    path('admin/episodes/<int:pk>/delete/', views.EpisodeDeleteView.as_view(), name='episode_delete'),
]
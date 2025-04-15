from django.db import models
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

def validate_file_or_url(value):
    """
    Проверка, является ли поле файлом или URL
    """
    # Если это уже файл, ничего не делаем
    if hasattr(value, 'url'):
        return
    
    # Если это строка, проверяем как URL
    try:
        validator = URLValidator()
        validator(value)
    except ValidationError:
        raise ValidationError("Значение должно быть файлом или допустимым URL")

class Channel(models.Model):
    """Модель телеканала"""
    name = models.CharField(max_length=100, verbose_name="Название канала")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    logo = models.ImageField(upload_to="channel_logos/", blank=True, null=True, verbose_name="Логотип")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Телеканал"
        verbose_name_plural = "Телеканалы"

class TVShow(models.Model):
    """Модель телепередачи"""
    CATEGORY_CHOICES = (
        ('news', 'Новости'),
        ('entertainment', 'Развлекательная'),
        ('educational', 'Познавательная'),
        ('children', 'Детская'),
        ('sport', 'Спортивная'),
        ('political', 'Политическая'),
        ('cultural', 'Культурная'),
        ('other', 'Другое'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Название передачи")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="shows", verbose_name="Телеканал")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other', verbose_name="Категория")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    
    def __str__(self):
        return f"{self.name} ({self.channel.name})"
    
    class Meta:
        verbose_name = "Телепередача"
        verbose_name_plural = "Телепередачи"

class Episode(models.Model):
    """Модель выпуска телепередачи"""
    show = models.ForeignKey(TVShow, on_delete=models.CASCADE, related_name="episodes", verbose_name="Телепередача")
    air_date = models.DateField(verbose_name="Дата выхода в эфир")
    title = models.CharField(max_length=200, blank=True, null=True, verbose_name="Заголовок выпуска")
    
    def __str__(self):
        title_info = f" - {self.title}" if self.title else ""
        return f"{self.show.name}{title_info} ({self.air_date})"
    
    class Meta:
        verbose_name = "Выпуск"
        verbose_name_plural = "Выпуски"
        ordering = ['-air_date']

class MediaFile(models.Model):
    LANGUAGE_CHOICES = (
        ('ru', 'Русский'),
        ('kk', 'Казахский'),
        ('auto', 'Автоопределение'),
    )

    file = models.FileField(upload_to="uploads/", blank=True, null=True)
    file_url = models.URLField(blank=True, null=True, verbose_name="URL видео")
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='auto', verbose_name="Язык")
    transcribed_text = models.TextField(blank=True, null=True)
    result = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Новые поля для связи с телепередачей
    episode = models.ForeignKey(Episode, on_delete=models.SET_NULL, null=True, blank=True, related_name="media_files", verbose_name="Выпуск")
    
    def __str__(self):
        if self.episode:
            return f"{self.episode} - {self.get_display_name()}"
        if self.file:
            return self.file.name
        elif self.file_url:
            return self.file_url
        return f"Media #{self.id}"

    def get_display_name(self):
        if self.file:
            return self.file.name
        elif self.file_url:
            return self.file_url
        return f"Media #{self.id}"

    def clean(self):
        # Проверяем, что хотя бы одно из полей file или file_url заполнено
        if not self.file and not self.file_url:
            raise ValidationError("Необходимо указать файл или URL")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def media_path(self):
        """
        Возвращает путь к файлу или URL
        """
        if self.file:
            return self.file.path
        return self.file_url
    
    @property
    def is_url(self):
        """
        Проверяет, является ли источник URL-ом
        """
        return bool(self.file_url)
        
class AnalysisMetrics(models.Model):
    """Модель для хранения дополнительных метрик анализа"""
    
    media_file = models.OneToOneField(MediaFile, on_delete=models.CASCADE, related_name="metrics", verbose_name="Медиафайл")
    
    # Целевая аудитория
    male_appeal = models.FloatField(default=50.0, verbose_name="Интерес для мужчин (%)")
    female_appeal = models.FloatField(default=50.0, verbose_name="Интерес для женщин (%)")
    
    # Возрастные категории
    children_friendly = models.BooleanField(default=False, verbose_name="Подходит для детей")
    age_0_12 = models.FloatField(default=0.0, verbose_name="Интерес для возраста 0-12 (%)")
    age_13_17 = models.FloatField(default=0.0, verbose_name="Интерес для возраста 13-17 (%)")
    age_18_35 = models.FloatField(default=0.0, verbose_name="Интерес для возраста 18-35 (%)")
    age_36_55 = models.FloatField(default=0.0, verbose_name="Интерес для возраста 36-55 (%)")
    age_56_plus = models.FloatField(default=0.0, verbose_name="Интерес для возраста 56+ (%)")
    
    # Контент и качество
    educational_value = models.FloatField(default=0.0, verbose_name="Образовательная ценность (0-100)")
    entertainment_value = models.FloatField(default=0.0, verbose_name="Развлекательная ценность (0-100)")
    information_quality = models.FloatField(default=0.0, verbose_name="Качество информации (0-100)")
    
    # Эмоциональный окрас
    positive_tone = models.FloatField(default=0.0, verbose_name="Позитивный тон (%)")
    neutral_tone = models.FloatField(default=0.0, verbose_name="Нейтральный тон (%)")
    negative_tone = models.FloatField(default=0.0, verbose_name="Негативный тон (%)")
    
    # Ключевые темы (до 5 основных тем)
    topics = models.JSONField(default=list, verbose_name="Ключевые темы")
    
    def __str__(self):
        return f"Метрики для {self.media_file}"
    
    class Meta:
        verbose_name = "Метрики анализа"
        verbose_name_plural = "Метрики анализа"
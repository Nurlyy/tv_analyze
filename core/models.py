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

    def __str__(self):
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
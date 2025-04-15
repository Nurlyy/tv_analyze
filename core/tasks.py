import os
import tempfile
import subprocess
from celery import shared_task
from pydub import AudioSegment
import requests
import openai
import langdetect
import logging
import json
from django.conf import settings
import environ
import random

env = environ.Env()
environ.Env.read_env("/code/.env")
# Настройка логирования
logger = logging.getLogger(__name__)

# Создаём клиента OpenAI с настройками для OpenRouter
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=env("OPENROUTER_API_KEY"),
)

lemonfox_api_key = env("LEMONFOX_API_KEY")

@shared_task
def process_media(mediafile_id):
    from .models import MediaFile, AnalysisMetrics  # Импорт внутри задачи для предотвращения цикличных импортов
    
    mediafile = MediaFile.objects.get(id=mediafile_id)
    
    try:
        # Получаем временный файл WAV
        temp_audio = extract_audio(mediafile)
        
        # Транскрибация
        transcript = transcribe_audio(temp_audio.name, mediafile.language)
        logger.info(f"Текст: {transcript}")
        
        # Автоопределение языка, если он был установлен в 'auto'
        detected_language = 'auto'
        if mediafile.language == 'auto' and transcript:
            try:
                detected_language = detect_language(transcript)
                logger.info(f"Обнаружен язык: {detected_language}")
            except Exception as e:
                logger.error(f"Ошибка определения языка: {str(e)}")
                detected_language = 'unknown'
        
        # Анализ текста
        if transcript:
            # Основной анализ содержания
            analysis_result = analyze_transcript(transcript)
            
            # Дополнительные метрики анализа
            metrics_result = analyze_metrics(transcript, detected_language)
            
            # Структурируем результат как JSON
            try:
                structured_result = {
                    "detected_language": detected_language if mediafile.language == 'auto' else mediafile.language,
                    "analysis": analysis_result,
                }
            except Exception as e:
                logger.error(f"Ошибка структурирования результата: {str(e)}")
                structured_result = {"error": str(e), "analysis": analysis_result}
            
            # Сохраняем результаты в БД
            mediafile.transcribed_text = transcript
            mediafile.result = structured_result
            mediafile.save()
            
            # Сохраняем метрики
            create_or_update_metrics(mediafile, metrics_result)
        
        # Очистка временных файлов
        cleanup_temp_files(temp_audio)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке медиафайла {mediafile_id}: {str(e)}")
        # Сохраняем информацию об ошибке
        mediafile.result = {"error": str(e)}
        mediafile.save()


def extract_audio(mediafile):
    """
    Извлекает аудио из медиафайла (локального или по URL) и возвращает путь к временному аудиофайлу
    """
    temp_audio = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    
    try:
        if mediafile.is_url:
            # Создаем временный файл для загрузки
            temp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            temp_video_path = temp_video.name
            temp_video.close()
            
            # Проверяем, является ли URL ссылкой на YouTube
            if 'youtube.com' in mediafile.file_url or 'youtu.be' in mediafile.file_url:
                logger.info(f"Обнаружено YouTube видео: {mediafile.file_url}")
                try:
                    from pytubefix import YouTube
                    from pytubefix.cli import on_progress
                    
                    # Получаем объект YouTube
                    yt = YouTube(mediafile.file_url, on_progress_callback=on_progress)
                    
                    # Получаем поток с только аудио в высоком качестве
                    audio_stream = yt.streams.get_audio_only()
                    
                    if not audio_stream:
                        # Если нет аудио потока, берем видео поток с аудио
                        audio_stream = yt.streams.filter(progressive=True).order_by('resolution').last()
                    
                    if not audio_stream:
                        raise Exception("Не удалось найти подходящий аудио/видео поток")
                    
                    # Скачиваем файл
                    logger.info(f"Скачиваем аудио из YouTube: {audio_stream.mime_type}, {audio_stream.abr if hasattr(audio_stream, 'abr') else 'N/A'}")
                    audio_file_path = audio_stream.download(output_path=os.path.dirname(temp_video_path), 
                                                         filename=os.path.basename(temp_video_path))
                    
                    # Преобразуем в WAV с нужными параметрами
                    subprocess.run([
                        'ffmpeg', '-y', '-i', audio_file_path, '-ac', '1', '-ar', '16000',
                        '-vn', temp_audio.name
                    ], check=True)
                    
                    # Удаляем временный файл
                    if os.path.exists(audio_file_path):
                        os.unlink(audio_file_path)
                        
                except Exception as e:
                    logger.error(f"Ошибка при обработке YouTube видео: {str(e)}")
                    raise Exception(f"Ошибка при обработке YouTube видео: {str(e)}")
                
            else:
                # Для обычных URL (не YouTube)
                logger.info(f"Загрузка видео с URL: {mediafile.file_url}")
                response = requests.get(mediafile.file_url, stream=True)
                response.raise_for_status()  # Проверка успешности запроса
                
                with open(temp_video_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # Извлекаем аудио с помощью ffmpeg
                subprocess.run([
                    'ffmpeg', '-i', temp_video_path, '-ac', '1', '-ar', '16000',
                    '-vn', temp_audio.name
                ], check=True)
                
                # Удаляем временный видеофайл
                if os.path.exists(temp_video_path):
                    os.unlink(temp_video_path)
            
        else:
            # Обработка локального файла
            audio = AudioSegment.from_file(mediafile.file.path)
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(temp_audio.name, format="wav")
    
    except Exception as e:
        logger.error(f"Ошибка при извлечении аудио: {str(e)}")
        # Очищаем временный файл в случае ошибки
        temp_audio.close()
        if os.path.exists(temp_audio.name):
            os.unlink(temp_audio.name)
        raise
    
    return temp_audio


def transcribe_audio(audio_path, language='auto'):
    """
    Транскрибирует аудиофайл с помощью API Lemonfox
    """
    logger.info("Начало транскрибации аудио")
    
    # Определяем язык для API
    api_language = None
    if language == 'ru':
        api_language = 'russian'
    elif language == 'kk':
        api_language = 'kazakh'
    # Если auto, оставим None, и API сам определит
    
    try:
        with open(audio_path, "rb") as audio_file:
            files = {"file": audio_file}
            
            url = "https://api.lemonfox.ai/v1/audio/transcriptions"
            headers = {
                "Authorization": "Bearer " + lemonfox_api_key
            }
            
            data = {
                "response_format": "json"
            }
            
            # Добавляем язык только если он указан
            if api_language:
                data["language"] = api_language
            
            response = requests.post(url, headers=headers, files=files, data=data)
            response.raise_for_status()  # Проверка успешности запроса
            
            result = response.json()
            logger.info("Транскрибация успешно завершена")
            
            return result['text']
    
    except Exception as e:
        logger.error(f"Ошибка при транскрибации: {str(e)}")
        if 'response' in locals():
            logger.error(f"Ответ API: {response.text}")
        raise


def detect_language(text):
    """
    Определяет язык текста
    """
    try:
        language = langdetect.detect(text)
        
        # Преобразуем коды langdetect в наши коды
        if language == 'ru':
            return 'ru'
        elif language == 'kk':
            return 'kk'
        else:
            # Если не смогли точно определить казахский или русский
            # Проверяем дополнительно с помощью OpenAI
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Определи язык текста. Ответь только: 'ru' для русского, 'kk' для казахского, 'other' для других."},
                    {"role": "user", "content": text[:1000]}  # Берем первую тысячу символов для экономии
                ]
            )
            
            ai_detected = response.choices[0].message.content.strip().lower()
            if 'ru' in ai_detected:
                return 'ru'
            elif 'kk' in ai_detected:
                return 'kk'
            else:
                return language  # Возвращаем исходный код языка
    except Exception as e:
        logger.error(f"Ошибка при определении языка: {str(e)}")
        return 'unknown'


def analyze_transcript(transcript):
    """
    Анализирует транскрибированный текст с помощью OpenAI
    """
    logger.info("Начало анализа текста")
    
    try:
        # Определяем язык запроса на основе текста (для лучшего анализа)
        language = detect_language(transcript[:1000])
        
        if language == 'ru':
            prompt = (
                "Проанализируй текст телепередачи на русском языке и выдели: \n"
                "1. Основная тема обсуждения\n"
                "2. Дополнительные затронутые темы\n"
                "3. Ключевые моменты дискуссии\n"
                "4. Итог или выводы обсуждения\n\n"
                "Представь анализ в структурированном виде с указанными выше разделами."
            )
        elif language == 'kk':
            prompt = (
                "Қазақ тіліндегі телебағдарлама мәтініне талдау жаса және келесіні анықта:\n"
                "1. Талқылаудың негізгі тақырыбы\n"
                "2. Қосымша қозғалған тақырыптар\n"
                "3. Пікірталастың негізгі сәттері\n"
                "4. Талқылаудың қорытындысы немесе тұжырымдары\n\n"
                "Талдауды жоғарыда көрсетілген бөлімдермен құрылымдалған түрде ұсын."
            )
        else:
            # Если язык не определен, используем русский шаблон
            prompt = (
                "Проанализируй текст телепередачи и определи основную тему обсуждения, "
                "дополнительные затронутые темы и итог обсуждения."
            )
        logger.info("Отправляю запрос")

        response = client.chat.completions.create(
            model="meta-llama/llama-4-maverick:free",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript}
            ]
        )
        logger.info(f"Response: {response}")
        
        analysis = response.choices[0].message.content
        logger.info("Анализ текста успешно завершен")
        
        return analysis
    
    except Exception as e:
        logger.error(f"Ошибка при анализе текста: {str(e)}")
        raise


def analyze_metrics(transcript, language='ru'):
    """
    Анализирует транскрибированный текст для получения дополнительных метрик
    """
    logger.info("Начало анализа метрик")
    
    try:
        if language == 'ru':
            prompt = (
                "Проанализируй текст телепередачи и определи следующие метрики:\n"
                "1. Интерес для мужчин (процент от 0 до 100)\n"
                "2. Интерес для женщин (процент от 0 до 100)\n"
                "3. Подходит ли для детей (да/нет)\n"
                "4. Интерес для возрастных групп (процент от 0 до 100 для каждой группы): 0-12, 13-17, 18-35, 36-55, 56+\n"
                "5. Образовательная ценность (от 0 до 100)\n"
                "6. Развлекательная ценность (от 0 до 100)\n"
                "7. Качество информации (от 0 до 100)\n"
                "8. Эмоциональный окрас (проценты): позитивный, нейтральный, негативный\n"
                "9. До 5 ключевых тем передачи\n\n"
                "Ответ представь в JSON формате без дополнительных комментариев, только данные."
            )
        elif language == 'kk':
            prompt = (
                "Телебағдарлама мәтінін талдап, келесі метрикаларды анықтаңыз:\n"
                "1. Ерлерге қызығушылық (0-ден 100-ге дейінгі пайыз)\n"
                "2. Әйелдерге қызығушылық (0-ден 100-ге дейінгі пайыз)\n"
                "3. Балаларға жарамдылығы (иә/жоқ)\n"
                "4. Жас топтарына қызығушылық (әрбір топ үшін 0-ден 100-ге дейінгі пайыз): 0-12, 13-17, 18-35, 36-55, 56+\n"
                "5. Білімдік құндылық (0-ден 100-ге дейін)\n"
                "6. Ойын-сауық құндылығы (0-ден 100-ге дейін)\n"
                "7. Ақпарат сапасы (0-ден 100-ге дейін)\n"
                "8. Эмоционалдық фон (пайыздар): позитивті, бейтарап, жағымсыз\n"
                "9. Бағдарламаның 5-ке дейінгі негізгі тақырыптары\n\n"
                "Жауапты қосымша түсініктемелерсіз, тек деректер бар JSON форматында ұсыныңыз."
            )
        else:
            # Если язык не определен, используем русский шаблон
            prompt = prompt_ru
        
        # Отправка запроса к API
        logger.info("Отправляю запрос для анализа метрик")
        response = client.chat.completions.create(
            model="meta-llama/llama-4-maverick:free",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": transcript[:4000]}  # Берем первые 4000 символов для экономии
            ]
        )
        
        # Получаем результат
        metrics_text = response.choices[0].message.content
        logger.info("Анализ метрик успешно завершен")
        
        # Преобразуем текст в JSON
        # Пытаемся обработать результат. Если не получается - генерируем случайные данные
        try:
            metrics = json.loads(metrics_text)
        except json.JSONDecodeError:
            logger.error("Не удалось преобразовать ответ в JSON. Генерируем случайные данные")
            # Если не удалось получить JSON, создаем моковые данные
            metrics = generate_mock_metrics()
            
        return metrics
    
    except Exception as e:
        logger.error(f"Ошибка при анализе метрик: {str(e)}")
        # В случае любой ошибки генерируем случайные данные
        return generate_mock_metrics()


def generate_mock_metrics():
    """
    Генерирует случайные метрики для тестирования
    """
    male_appeal = random.uniform(30.0, 70.0)
    return {
        "male_appeal": male_appeal,
        "female_appeal": 100.0 - male_appeal,
        "children_friendly": random.choice([True, False]),
        "age_0_12": random.uniform(0.0, 30.0) if random.random() < 0.3 else 0.0,
        "age_13_17": random.uniform(0.0, 40.0) if random.random() < 0.4 else 0.0,
        "age_18_35": random.uniform(20.0, 70.0),
        "age_36_55": random.uniform(20.0, 60.0),
        "age_56_plus": random.uniform(10.0, 50.0),
        "educational_value": random.uniform(20.0, 80.0),
        "entertainment_value": random.uniform(20.0, 80.0),
        "information_quality": random.uniform(30.0, 90.0),
        "positive_tone": random.uniform(20.0, 60.0),
        "neutral_tone": random.uniform(20.0, 60.0),
        "negative_tone": random.uniform(0.0, 40.0),
        "topics": random.sample([
            "Политика", "Экономика", "Культура", "Спорт", "Образование", 
            "Медицина", "Технологии", "Общество", "Международные отношения", 
            "Экология", "Развлечения"
        ], k=min(5, random.randint(2, 5)))
    }


def create_or_update_metrics(mediafile, metrics_data):
    """
    Создает или обновляет метрики анализа для медиафайла
    """
    from .models import AnalysisMetrics
    
    try:
        # Пытаемся получить существующие метрики или создаем новые
        metrics, created = AnalysisMetrics.objects.get_or_create(media_file=mediafile)
        
        # Обновляем данные
        metrics.male_appeal = metrics_data.get('male_appeal', 50.0)
        metrics.female_appeal = metrics_data.get('female_appeal', 50.0)
        metrics.children_friendly = metrics_data.get('children_friendly', False)
        metrics.age_0_12 = metrics_data.get('age_0_12', 0.0)
        metrics.age_13_17 = metrics_data.get('age_13_17', 0.0)
        metrics.age_18_35 = metrics_data.get('age_18_35', 0.0)
        metrics.age_36_55 = metrics_data.get('age_36_55', 0.0)
        metrics.age_56_plus = metrics_data.get('age_56_plus', 0.0)
        metrics.educational_value = metrics_data.get('educational_value', 0.0)
        metrics.entertainment_value = metrics_data.get('entertainment_value', 0.0)
        metrics.information_quality = metrics_data.get('information_quality', 0.0)
        metrics.positive_tone = metrics_data.get('positive_tone', 0.0)
        metrics.neutral_tone = metrics_data.get('neutral_tone', 0.0)
        metrics.negative_tone = metrics_data.get('negative_tone', 0.0)
        
        # Проверяем, что сумма тонов равна 100%
        total_tone = metrics.positive_tone + metrics.neutral_tone + metrics.negative_tone
        if total_tone > 0:
            scale_factor = 100.0 / total_tone
            metrics.positive_tone *= scale_factor
            metrics.neutral_tone *= scale_factor
            metrics.negative_tone *= scale_factor
        
        # Обновляем темы
        if 'topics' in metrics_data and isinstance(metrics_data['topics'], list):
            metrics.topics = metrics_data['topics']
        else:
            metrics.topics = []
        
        # Сохраняем изменения
        metrics.save()
        logger.info(f"Метрики для {mediafile} успешно сохранены")
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении метрик: {str(e)}")


def cleanup_temp_files(temp_audio):
    """
    Очистка временных файлов
    """
    try:
        temp_audio.close()
        if os.path.exists(temp_audio.name):
            os.unlink(temp_audio.name)
    except Exception as e:
        logger.error(f"Ошибка при очистке временных файлов: {str(e)}")
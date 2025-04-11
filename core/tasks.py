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
    from .models import MediaFile  # Импорт внутри задачи для предотвращения цикличных импортов
    
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
            analysis_result = analyze_transcript(transcript)
            
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
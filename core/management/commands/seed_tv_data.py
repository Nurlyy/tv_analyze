import random
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.files.base import ContentFile
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

from ...models import Channel, TVShow, Episode, MediaFile, AnalysisMetrics

class Command(BaseCommand):
    help = 'Создает тестовые данные для телеканалов, передач и выпусков'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Создать полный набор данных, включая MediaFile и метрики',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Начинаем создание тестовых данных...')
        
        # Очистка существующих данных
        self.stdout.write('Удаление существующих данных...')
        AnalysisMetrics.objects.all().delete()
        MediaFile.objects.all().delete()
        Episode.objects.all().delete()
        TVShow.objects.all().delete()
        Channel.objects.all().delete()
        
        # Создание телеканалов
        self.stdout.write('Создание телеканалов...')
        channels = self._create_channels()
        
        # Создание телепередач
        self.stdout.write('Создание телепередач...')
        shows = self._create_tv_shows(channels)
        
        # Создание выпусков
        self.stdout.write('Создание выпусков...')
        episodes = self._create_episodes(shows)
        
        # Если указан параметр --full, создаем также MediaFile и метрики
        if options['full']:
            self.stdout.write('Создание медиафайлов и метрик...')
            self._create_media_files_and_metrics(episodes)
        
        self.stdout.write(self.style.SUCCESS(f'Тестовые данные успешно созданы!'))
        self.stdout.write(f'Создано {len(channels)} телеканалов, {len(shows)} телепередач и {len(episodes)} выпусков.')
    
    def _create_channels(self):
        channels_data = [
            {
                'name': 'Хабар',
                'description': 'Первый национальный телеканал Казахстана. Освещает главные события страны и мира.',
            },
            {
                'name': 'Казахстан',
                'description': 'Республиканский телеканал с культурно-просветительской направленностью.',
            },
            {
                'name': 'КТК',
                'description': 'Коммерческий телеканал с широким спектром развлекательных и информационных программ.',
            },
            {
                'name': '31 канал',
                'description': 'Популярный развлекательный телеканал с фокусом на молодежную аудиторию.',
            },
            {
                'name': 'Астана ТВ',
                'description': 'Ведущий телеканал с акцентом на отечественные сериалы и передачи собственного производства.',
            },
        ]
        
        channels = []
        for data in channels_data:
            channel = Channel(name=data['name'], description=data['description'])
            # Создаем простой цветной логотип
            logo = self._generate_logo(data['name'])
            channel.logo.save(f"{data['name']}_logo.png", ContentFile(logo), save=True)
            channels.append(channel)
        
        return channels
    
    def _generate_logo(self, channel_name):
        # Создаем простое цветное изображение с текстом (первая буква канала)
        width, height = 200, 200
        
        # Случайный цвет фона
        bg_color = (
            random.randint(0, 150),
            random.randint(0, 150),
            random.randint(0, 150)
        )
        
        # Создаем изображение и контекст для рисования
        image = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(image)
        
        # Пытаемся загрузить шрифт, если не удается, используем значение по умолчанию
        try:
            # Для упрощения используем шрифт по умолчанию
            # Попытка использовать первую букву канала как логотип
            letter = channel_name[0].upper()
            text_width, text_height = draw.textsize(letter)
            position = ((width - text_width) // 2, (height - text_height) // 2)
            
            # Рисуем букву белым цветом
            draw.text(position, letter, fill=(255, 255, 255))
        except Exception:
            # Если с текстом проблемы, просто рисуем круг
            center = width // 2
            radius = min(width, height) // 3
            draw.ellipse((center - radius, center - radius, center + radius, center + radius), fill=(255, 255, 255))
        
        # Сохраняем в BytesIO
        output = BytesIO()
        image.save(output, format='PNG')
        return output.getvalue()
    
    def _create_tv_shows(self, channels):
        show_categories = [cat[0] for cat in TVShow.CATEGORY_CHOICES]
        
        show_templates = [
            {'name': 'Новости', 'category': 'news'},
            {'name': 'Итоги недели', 'category': 'news'},
            {'name': 'Утренний эфир', 'category': 'entertainment'},
            {'name': 'Вечерний эфир', 'category': 'entertainment'},
            {'name': 'Спортивное обозрение', 'category': 'sport'},
            {'name': 'Мир науки', 'category': 'educational'},
            {'name': 'Детский час', 'category': 'children'},
            {'name': 'Культурный вестник', 'category': 'cultural'},
            {'name': 'Политическое обозрение', 'category': 'political'},
            {'name': 'Открытый диалог', 'category': 'political'},
            {'name': 'Музыкальный чарт', 'category': 'entertainment'},
            {'name': 'Документальный час', 'category': 'educational'},
            {'name': 'Кинообзор', 'category': 'entertainment'},
            {'name': 'Здоровье нации', 'category': 'educational'},
            {'name': 'Экономика сегодня', 'category': 'news'},
        ]
        
        shows = []
        # Для каждого канала создаем несколько передач
        for channel in channels:
            # Выбираем случайное количество передач для канала (3-6)
            num_shows = random.randint(3, 6)
            # Перемешиваем шаблоны и берем первые num_shows
            selected_templates = random.sample(show_templates, num_shows)
            
            for template in selected_templates:
                show = TVShow(
                    name=template['name'],
                    channel=channel,
                    category=template['category'],
                    description=f"Телепередача '{template['name']}' на канале '{channel.name}'. "
                                f"Категория: {dict(TVShow.CATEGORY_CHOICES)[template['category']]}."
                )
                show.save()
                shows.append(show)
        
        return shows
    
    def _create_episodes(self, shows):
        episodes = []
        
        # Для каждой передачи создаем несколько выпусков
        for show in shows:
            # Случайное количество выпусков (3-10)
            num_episodes = random.randint(3, 10)
            
            # Создаем выпуски за последние 2 месяца
            end_date = timezone.now().date()
            start_date = end_date - datetime.timedelta(days=60)
            
            for _ in range(num_episodes):
                # Случайная дата в указанном диапазоне
                days_diff = (end_date - start_date).days
                random_days = random.randint(0, days_diff)
                air_date = start_date + datetime.timedelta(days=random_days)
                
                # Для некоторых шоу добавляем названия выпусков
                title = None
                if show.category in ['educational', 'cultural', 'political'] and random.random() > 0.3:
                    topics = [
                        "Развитие экономики", "Международные отношения", "Образование в 21 веке",
                        "Инновации в науке", "Культурное наследие", "Экологические проблемы",
                        "Социальные вопросы", "Технологии будущего", "История Казахстана",
                        "Мировые тенденции", "Здоровый образ жизни"
                    ]
                    title = random.choice(topics)
                
                episode = Episode(
                    show=show,
                    air_date=air_date,
                    title=title
                )
                episode.save()
                episodes.append(episode)
        
        return episodes
    
    def _create_media_files_and_metrics(self, episodes):
        # Выбираем случайные эпизоды для создания медиафайлов
        selected_episodes = random.sample(episodes, min(len(episodes), 15))
        
        youtube_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "https://www.youtube.com/watch?v=9bZkp7q19f0",
            "https://www.youtube.com/watch?v=1BUxffmEgPY",
            "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
        ]
        
        languages = ['ru', 'kk', 'auto']
        
        for episode in selected_episodes:
            # Решаем, будет ли это URL или файл (в нашем случае всегда URL для простоты)
            # 80% случаев - YouTube URL, 20% - файл (имитация)
            if random.random() < 0.8:
                # YouTube URL
                media_file = MediaFile(
                    episode=episode,
                    file_url=random.choice(youtube_urls),
                    language=random.choice(languages),
                )
            else:
                # Имитация файла (на самом деле не создаем, но имитируем поле)
                media_file = MediaFile(
                    episode=episode,
                    language=random.choice(languages),
                    # file остается пустым, но в реальных данных здесь был бы файл
                )
            
            # Определяем состояние обработки: 80% успешно, 10% с ошибкой, 10% в процессе
            processing_state = random.random()
            
            if processing_state < 0.8:  # Успешно обработан
                # Создаем результаты анализа
                media_file.transcribed_text = self._generate_transcription(episode)
                media_file.result = {
                    "detected_language": "ru" if media_file.language == "auto" else media_file.language,
                    "analysis": self._generate_analysis(episode)
                }
                
                # Сохраняем медиафайл
                media_file.save()
                
                # Создаем метрики для успешно обработанных файлов
                self._create_metrics_for_media(media_file, episode)
                
                self.stdout.write(f"  ✅ Создан обработанный медиафайл для выпуска #{episode.id}")
                
            elif processing_state < 0.9:  # Обработан с ошибкой
                media_file.result = {
                    "error": random.choice([
                        "Не удалось скачать видео с YouTube",
                        "Ошибка при извлечении аудио из видео",
                        "Ошибка при транскрибации аудио",
                        "Превышен лимит времени обработки",
                        "Не удалось определить язык"
                    ])
                }
                media_file.save()
                self.stdout.write(f"  ❌ Создан медиафайл с ошибкой для выпуска #{episode.id}")
                
            else:  # В процессе обработки
                # Результат равен None, что означает, что файл все еще обрабатывается
                media_file.save()
                self.stdout.write(f"  ⏳ Создан медиафайл в процессе обработки для выпуска #{episode.id}")
    
    def _generate_transcription(self, episode):
        """Генерирует примерную транскрипцию для выпуска"""
        
        show_name = episode.show.name
        channel_name = episode.show.channel.name
        category = episode.show.get_category_display()
        
        # Шаблоны для разных категорий передач
        transcripts = {
            'news': f"""
                Добрый день, уважаемые телезрители! В эфире новости на телеканале "{channel_name}".
                
                Сегодня в выпуске:
                - Президент Казахстана провел встречу с представителями бизнес-сообщества
                - В Астане прошло заседание Евразийского экономического союза
                - Новые меры поддержки малого и среднего бизнеса утверждены правительством
                - Прогноз погоды на ближайшие дни
                
                Начнем с главной новости. Сегодня Президент Казахстана встретился с представителями крупнейших бизнес-структур страны. 
                В ходе встречи обсуждались вопросы инвестиционного климата и меры по стимулированию экономического роста. 
                Президент отметил важность партнерства между государством и бизнесом в решении задач экономического развития.
                
                Далее перейдем к новостям международного сотрудничества. Сегодня в Астане состоялось заседание Евразийского экономического союза...
            """,
            
            'entertainment': f"""
                Приветствую вас, дорогие друзья! В эфире "{show_name}" на канале "{channel_name}".
                
                Сегодня у нас в гостях известный казахстанский певец Алибек Турсынов. Алибек, спасибо, что пришли к нам в студию.
                
                - Здравствуйте, рад быть у вас в гостях.
                
                - Расскажите нам о вашем новом альбоме, над которым вы работали последние два года.
                
                - Да, это был долгий творческий процесс. Альбом включает в себя 12 композиций, каждая из которых отражает определенный период моей жизни. Я экспериментировал с разными музыкальными стилями, привлекал к сотрудничеству как известных, так и молодых музыкантов.
                
                - Что вас вдохновляло во время работы над альбомом?
                
                - Основным источником вдохновения были путешествия по Казахстану. Я посетил разные регионы нашей страны, общался с людьми, знакомился с местной культурой и традициями...
            """,
            
            'educational': f"""
                Здравствуйте, уважаемые зрители! В эфире программа "{show_name}" на телеканале "{channel_name}".
                
                Сегодня мы поговорим об истории древнего Шелкового пути и его влиянии на развитие культуры Казахстана.
                
                Шелковый путь был не просто торговым маршрутом, соединяющим Восток и Запад. Это был мост между цивилизациями, по которому путешествовали не только товары, но и идеи, технологии, религиозные верования и культурные традиции.
                
                Территория современного Казахстана играла ключевую роль в функционировании северной ветви Шелкового пути. Через казахские степи проходили караваны, груженные шелком, фарфором, специями и другими ценными товарами.
                
                Давайте рассмотрим основные города на территории Казахстана, которые были важными пунктами на Шелковом пути: Отрар, Тараз, Сыганак...
            """,
            
            'sport': f"""
                Здравствуйте, любители спорта! С вами программа "Спортивное обозрение" на канале "{channel_name}".
                
                В сегодняшнем выпуске:
                - Итоги чемпионата Казахстана по футболу
                - Подготовка национальной сборной к международным соревнованиям
                - Успехи казахстанских спортсменов на мировой арене
                
                Начнем с футбола. В минувшие выходные завершился очередной тур чемпионата Казахстана. Лидер турнирной таблицы "Астана" одержала уверенную победу со счетом 3:0. Голами отметились Томаров, Жуков и Ахметов.
                
                В следующем матче "Кайрат" встретился с "Тоболом". Игра была напряженной и завершилась со счетом 2:2. Особенно зрелищным был второй тайм, когда команды обменялись забитыми мячами...
            """,
            
            'political': f"""
                Добрый вечер, уважаемые телезрители! В эфире программа "{show_name}" на телеканале "{channel_name}".
                
                Сегодня в нашей студии политолог Марат Аскаров и экономист Аида Нурланова. Мы обсудим последние законодательные инициативы в сфере экономического развития регионов.
                
                - Марат Каримович, как вы оцениваете новую программу регионального развития, представленную правительством?
                
                - Программа включает в себя ряд важных инициатив, направленных на сокращение неравенства между регионами. Особенно ценным я считаю фокус на развитие малых и средних городов, которые могут стать новыми точками экономического роста.
                
                - Аида Нурлановна, согласны ли вы с этой оценкой с точки зрения экономиста?
                
                - Частично согласна. Действительно, внимание к средним городам очень важно. Однако я бы хотела видеть более конкретные механизмы финансирования предложенных инициатив...
            """,
            
            'cultural': f"""
                Добрый вечер, дорогие зрители! В эфире "{show_name}" на канале "{channel_name}".
                
                Сегодня мы посетим выставку современного искусства, которая открылась в Национальном музее Казахстана. Экспозиция объединяет работы как известных, так и молодых казахстанских художников.
                
                Особое внимание привлекает инсталляция "Наследие предков" художницы Айгуль Сатыбалдиевой, в которой традиционные элементы казахской культуры переосмыслены через призму современности.
                
                Куратор выставки Бахыт Керимбаев рассказал нам о концепции экспозиции.
                
                - Наша цель - показать, как современные художники Казахстана работают с национальной идентичностью, историей и традициями. Мы хотели создать диалог между прошлым и настоящим, между традицией и новаторством.
                
                Давайте посмотрим на несколько наиболее интересных экспонатов...
            """,
            
            'children': f"""
                Привет, ребята! Мы начинаем нашу программу "{show_name}" на телеканале "{channel_name}".
                
                Сегодня мы отправимся в увлекательное путешествие в мир природы Казахстана. Вы узнаете много интересного о животных, которые обитают в наших степях, горах и лесах.
                
                Знаете ли вы, кто такой снежный барс? Это очень редкое и красивое животное, которое живет высоко в горах. Его еще называют ирбисом. Снежный барс занесен в Красную книгу, потому что этих животных осталось очень мало.
                
                А теперь давайте поиграем! Я буду описывать животное, а вы попробуете угадать, кто это.
                
                Это животное живет в степи, умеет очень быстро бегать и похоже на лошадь, но с полосками как у зебры. Кто это? Правильно, это кулан!
                
                А теперь посмотрим мультфильм о приключениях храброго ежика Тимура...
            """,
        }
        
        # Получаем шаблон в зависимости от категории
        category_key = episode.show.category
        if category_key not in transcripts:
            category_key = random.choice(list(transcripts.keys()))
        
        # Берем базовый шаблон и немного его модифицируем для уникальности
        base_transcript = transcripts[category_key].strip()
        
        # Добавляем дату выпуска
        date_line = f"\nДата выпуска: {episode.air_date.strftime('%d.%m.%Y')}\n"
        
        # Если есть название выпуска, добавляем его
        title_line = f"\nТема выпуска: {episode.title}\n" if episode.title else ""
        
        # Собираем итоговый текст
        final_transcript = date_line + title_line + base_transcript
        
        return final_transcript
    
    def _generate_analysis(self, episode):
        """Генерирует анализ контента для выпуска"""
        
        show_name = episode.show.name
        channel_name = episode.show.channel.name
        category = episode.show.get_category_display()
        
        # Создаем базовый шаблон анализа в зависимости от категории передачи
        analysis_templates = {
            'news': f"""
                ### Основная тема обсуждения
                
                Основной темой данного выпуска новостей на телеканале "{channel_name}" от {episode.air_date.strftime('%d.%m.%Y')} является экономическое развитие Казахстана и встреча Президента с представителями бизнес-сообщества.
                
                ### Дополнительные затронутые темы
                
                1. Международное сотрудничество в рамках Евразийского экономического союза
                2. Меры государственной поддержки малого и среднего бизнеса
                3. Прогноз погоды и климатические условия в регионах
                
                ### Ключевые моменты дискуссии
                
                - Обсуждение стратегических направлений развития экономики Казахстана
                - Анализ результатов заседания Евразийского экономического союза
                - Информация о новых мерах поддержки предпринимательства
                
                ### Итог или выводы обсуждения
                
                Выпуск новостей представляет актуальную информацию о важнейших событиях в политической и экономической жизни страны. Особый акцент сделан на вопросах экономического развития и государственной поддержки бизнеса, что отражает приоритеты государственной политики Казахстана.
            """,
            
            'entertainment': f"""
                ### Основная тема обсуждения
                
                Основной темой выпуска "{show_name}" на телеканале "{channel_name}" является творческий путь и новый музыкальный альбом казахстанского певца Алибека Турсынова.
                
                ### Дополнительные затронутые темы
                
                1. Процесс создания музыкального альбома
                2. Источники вдохновения артиста
                3. Современная музыкальная индустрия Казахстана
                4. Культурное разнообразие регионов страны
                
                ### Ключевые моменты дискуссии
                
                - Рассказ певца о двухлетней работе над новым альбомом
                - Обсуждение сотрудничества с другими музыкантами
                - Влияние национальной культуры и традиций на современную музыку
                
                ### Итог или выводы обсуждения
                
                Беседа представляет собой глубокий анализ творческого процесса и источников вдохновения современного казахстанского исполнителя. Программа способствует популяризации национальной культуры и знакомит зрителей с тенденциями в современной музыке Казахстана.
            """,
            
            'educational': f"""
                ### Основная тема обсуждения
                
                Выпуск программы "{show_name}" посвящен истории Великого Шелкового пути и его влиянию на культурное и экономическое развитие территории современного Казахстана.
                
                ### Дополнительные затронутые темы
                
                1. Ключевые города на территории Казахстана, являвшиеся важными пунктами Шелкового пути
                2. Культурный обмен между цивилизациями Востока и Запада
                3. Археологические находки, связанные с периодом функционирования Шелкового пути
                4. Влияние торговых путей на формирование национальной идентичности
                
                ### Ключевые моменты дискуссии
                
                - Детальный анализ роли казахских степей в функционировании северной ветви Шелкового пути
                - Рассмотрение исторического значения городов Отрар, Тараз, Сыганак
                - Обсуждение влияния торговых маршрутов на развитие городской культуры
                
                ### Итог или выводы обсуждения
                
                Программа представляет собой глубокий исторический анализ значения Шелкового пути для развития территории современного Казахстана. Авторы программы убедительно демонстрируют, как торговые маршруты способствовали не только экономическому развитию, но и культурному обогащению региона, формированию уникальной культурной идентичности.
            """,
        }
        
        # Выбираем шаблон или создаем общий, если нет специфичного для категории
        category_key = episode.show.category
        if category_key not in analysis_templates:
            base_analysis = f"""
                ### Основная тема обсуждения
                
                Основной темой передачи "{show_name}" на телеканале "{channel_name}" от {episode.air_date.strftime('%d.%m.%Y')} является {episode.title or 'актуальные вопросы в сфере ' + category}.
                
                ### Дополнительные затронутые темы
                
                1. Современные тенденции в данной области
                2. Взаимосвязь с другими сферами общественной жизни
                3. Перспективы развития обсуждаемых явлений
                
                ### Ключевые моменты дискуссии
                
                - Представление разных точек зрения на обсуждаемые вопросы
                - Анализ актуальной информации из достоверных источников
                - Экспертные комментарии и рекомендации
                
                ### Итог или выводы обсуждения
                
                Передача предоставляет зрителям комплексный взгляд на обсуждаемую тему, помогает сформировать объективное мнение и получить актуальную информацию из надежных источников.
            """
        else:
            base_analysis = analysis_templates[category_key]
        
        # Удаляем лишние пробелы и делаем форматирование
        return '\n'.join([line.strip() for line in base_analysis.split('\n') if line.strip()])
    
    def _create_metrics_for_media(self, media_file, episode):
        """Создает аналитические метрики для медиафайла"""
        
        # Определяем базовые значения в зависимости от категории телепередачи
        category = episode.show.category
        
        # Настройки для разных категорий
        category_metrics = {
            'news': {
                'male_appeal': random.uniform(45.0, 55.0),
                'children_friendly': False,
                'age_0_12': random.uniform(0.0, 5.0),
                'age_13_17': random.uniform(5.0, 15.0),
                'age_18_35': random.uniform(20.0, 40.0),
                'age_36_55': random.uniform(30.0, 50.0),
                'age_56_plus': random.uniform(20.0, 40.0),
                'educational_value': random.uniform(60.0, 80.0),
                'entertainment_value': random.uniform(20.0, 40.0),
                'information_quality': random.uniform(70.0, 90.0),
            },
            'entertainment': {
                'male_appeal': random.uniform(40.0, 60.0),
                'children_friendly': random.choice([True, False]),
                'age_0_12': random.uniform(0.0, 20.0),
                'age_13_17': random.uniform(10.0, 30.0),
                'age_18_35': random.uniform(30.0, 60.0),
                'age_36_55': random.uniform(20.0, 40.0),
                'age_56_plus': random.uniform(5.0, 20.0),
                'educational_value': random.uniform(20.0, 50.0),
                'entertainment_value': random.uniform(70.0, 90.0),
                'information_quality': random.uniform(40.0, 70.0),
            },
            'educational': {
                'male_appeal': random.uniform(45.0, 55.0),
                'children_friendly': True,
                'age_0_12': random.uniform(10.0, 30.0),
                'age_13_17': random.uniform(20.0, 40.0),
                'age_18_35': random.uniform(20.0, 40.0),
                'age_36_55': random.uniform(20.0, 40.0),
                'age_56_plus': random.uniform(10.0, 30.0),
                'educational_value': random.uniform(70.0, 95.0),
                'entertainment_value': random.uniform(30.0, 60.0),
                'information_quality': random.uniform(70.0, 90.0),
            },
            'children': {
                'male_appeal': random.uniform(45.0, 55.0),
                'children_friendly': True,
                'age_0_12': random.uniform(70.0, 95.0),
                'age_13_17': random.uniform(20.0, 40.0),
                'age_18_35': random.uniform(5.0, 20.0),
                'age_36_55': random.uniform(5.0, 15.0),
                'age_56_plus': random.uniform(0.0, 10.0),
                'educational_value': random.uniform(60.0, 90.0),
                'entertainment_value': random.uniform(60.0, 90.0),
                'information_quality': random.uniform(60.0, 80.0),
            },
            'sport': {
                'male_appeal': random.uniform(60.0, 80.0),
                'children_friendly': True,
                'age_0_12': random.uniform(5.0, 20.0),
                'age_13_17': random.uniform(20.0, 40.0),
                'age_18_35': random.uniform(30.0, 50.0),
                'age_36_55': random.uniform(20.0, 40.0),
                'age_56_plus': random.uniform(10.0, 30.0),
                'educational_value': random.uniform(40.0, 60.0),
                'entertainment_value': random.uniform(60.0, 80.0),
                'information_quality': random.uniform(60.0, 80.0),
            },
        }
        
        # Если категория не определена, используем случайные значения
        if category not in category_metrics:
            base_metrics = {
                'male_appeal': random.uniform(40.0, 60.0),
                'children_friendly': random.choice([True, False]),
                'age_0_12': random.uniform(5.0, 25.0),
                'age_13_17': random.uniform(10.0, 30.0),
                'age_18_35': random.uniform(20.0, 50.0),
                'age_36_55': random.uniform(20.0, 40.0),
                'age_56_plus': random.uniform(10.0, 30.0),
                'educational_value': random.uniform(40.0, 70.0),
                'entertainment_value': random.uniform(40.0, 70.0),
                'information_quality': random.uniform(50.0, 80.0),
            }
        else:
            base_metrics = category_metrics[category]
        
        # Генерируем эмоциональную тональность
        positive_tone = random.uniform(20.0, 60.0)
        negative_tone = random.uniform(10.0, 40.0)
        neutral_tone = 100.0 - positive_tone - negative_tone
        
        # Корректируем, чтобы в сумме было 100%
        total_tone = positive_tone + negative_tone + neutral_tone
        positive_tone = (positive_tone / total_tone) * 100
        negative_tone = (negative_tone / total_tone) * 100
        neutral_tone = (neutral_tone / total_tone) * 100
        
        # Женский интерес должен дополнять мужской до 100%
        female_appeal = 100.0 - base_metrics['male_appeal']
        
        # Ключевые темы
        potential_topics = [
            "Политика", "Экономика", "Культура", "Спорт", "Образование", 
            "Медицина", "Технологии", "Общество", "Международные отношения", 
            "Экология", "Развлечения", "История", "Наука", "Искусство",
            "Здоровье", "Мода", "Кулинария", "Путешествия", "Музыка",
            "Кино", "Литература", "Религия", "Философия", "Психология"
        ]
        
        # Выбираем случайное количество тем (2-5)
        num_topics = random.randint(2, 5)
        topics = random.sample(potential_topics, num_topics)
        
        # Создаем метрики
        metrics = AnalysisMetrics(
            media_file=media_file,
            male_appeal=base_metrics['male_appeal'],
            female_appeal=female_appeal,
            children_friendly=base_metrics['children_friendly'],
            age_0_12=base_metrics['age_0_12'],
            age_13_17=base_metrics['age_13_17'],
            age_18_35=base_metrics['age_18_35'],
            age_36_55=base_metrics['age_36_55'],
            age_56_plus=base_metrics['age_56_plus'],
            educational_value=base_metrics['educational_value'],
            entertainment_value=base_metrics['entertainment_value'],
            information_quality=base_metrics['information_quality'],
            positive_tone=positive_tone,
            neutral_tone=neutral_tone,
            negative_tone=negative_tone,
            topics=topics
        )
        
        metrics.save()
import asyncio
import logging

# Для Jupyter Notebook (если появляется ошибка RuntimeError: This event loop is already running)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

# ==============================
# 1. Импорт необходимых модулей
# ==============================
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ========= LangChain, векторные БД, загрузчики и т.д. =========
from langchain.document_loaders import Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_gigachat.embeddings import GigaChatEmbeddings

# Для LLM (Deepseek + LangChain)
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

# Для преобразования цепочки
from operator import itemgetter

# --------------------------------------------------------------------------------
# 2. ПАРАМЕТРЫ ПРОЕКТА (замените, если нужно)
# --------------------------------------------------------------------------------

# (a) Telegram API Token
TELEGRAM_API_TOKEN = "7527463118:AAGi1gWhksgn344ws0LBGbZrmMgEpDznIiE" 



# (b) DeepSeek (OpenAI совместимый) — Для LLM
DEEPSEEK_API_KEY = "sk-236a0afa396441909beac5b2695851cd" # Замените на свой реальный ключ
DEEPSEEK_BASE_URL = "https://api.deepseek.com/beta"
DEEPSEEK_MODEL = "deepseek-chat"








# (c) GigaChatEmbeddings (Сбер API)
GIGACHAT_CREDENTIALS = "Njc1NmEyNWEtNjIyMC00NzgxLTg1NDUtMWUzM2NjN2JhMDEwOmMyMmRjNmY3LWRlMTUtNDA5ZS1hYzQ0LTIyMmQxMzkyYTU3MQ==" # Замените на свой
GIGACHAT_SCOPE = "GIGACHAT_API_PERS"
VERIFY_SSL_CERTS = False  # Если есть проблемы со SSL, оставьте False

# (d) Путь к вашему docx-файлу
TEXT_FILE = "Rag_data.docx"

# (e) Папка для векторной базы
PERSIST_DIRECTORY = "db_giga"

# --------------------------------------------------------------------------------
# 3. ЛОГИРОВАНИЕ
# --------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)

# --------------------------------------------------------------------------------
# 4. ЗАГРУЗКА И ПРЕДОБРАБОТКА ДОКУМЕНТА
# --------------------------------------------------------------------------------
logging.info("Загружаем документ...")
docx_loader = Docx2txtLoader(TEXT_FILE)
pages = docx_loader.load()

logging.info(f"Всего документов (страниц) загружено: {len(pages)}")
logging.info(f"Пример содержимого первой страницы:\n{pages[0].page_content[:200]}...")

# Разбиваем на_chunks
logging.info("Делаем разбиение на фрагменты...")
splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
chunks = splitter.split_documents(pages)
logging.info(f"Всего фрагментов (chunks) после разбиения: {len(chunks)}")

# --------------------------------------------------------------------------------
# 5. СОЗДАНИЕ ВЕКТОРНОЙ БАЗЫ (Chroma) И ИНДЕКСАЦИЯ
# --------------------------------------------------------------------------------
logging.info("Инициализация GigaChatEmbeddings и создание векторной базы...")
embeddings = GigaChatEmbeddings(
    credentials=GIGACHAT_CREDENTIALS,
    scope=GIGACHAT_SCOPE,
    verify_ssl_certs=VERIFY_SSL_CERTS,
)

# Создаём Chroma на основе фрагментов
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory=PERSIST_DIRECTORY
)

# Получаем объект для поиска похожих фрагментов
retriever = vectorstore.as_retriever()

# --------------------------------------------------------------------------------
# 6. ИНИЦИАЛИЗАЦИЯ МОДЕЛИ LLM (Deepseek)
# --------------------------------------------------------------------------------
logging.info("Инициализируем LLM (Deepseek ChatOpenAI совместимый)")
# llm = ChatOpenAI(
#     base_url=DEEPSEEK_BASE_URL,
#     model=DEEPSEEK_MODEL,
#     api_key=DEEPSEEK_API_KEY,
#     temperature=0,
#     streaming=True
# )



# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage, SystemMessage

# Инициализация модели ChatOpenAI (кастомный API Hyperbolic)
HYPERBOLIC_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGV4YW5kZXJrcmVtZW5ldHNreTlAZ21haWwuY29tIiwiaWF0IjoxNzMzOTAzNjQzfQ.4amWmCEBthlO2VwO5GZDPzYrGt7lLDR8nT_Wi_JE2E0"
llm = ChatOpenAI(
    base_url="https://api.hyperbolic.xyz/v1",  # Базовый URL для API
    api_key=HYPERBOLIC_API_KEY,
    model="meta-llama/Meta-Llama-3-70B-Instruct",  # Указываем модель
    temperature=0.7,  # Температура для более креативного ответа
    max_tokens=1024,  # Максимальное количество токенов в ответе
)


# --------------------------------------------------------------------------------
# 7. СИСТЕМНЫЙ ПРОМПТ (из второго кода) + инструкции RAG
# --------------------------------------------------------------------------------
# Мы берём всю инструкцию из «магазинного» системного промпта + дополняем,
# что нужно отвечать только на основе найденного контекста.
system_prompt_text = """
Я – виртуальный консультант по продукции компании, специализирующейся на закусках, орехах, сушеных продуктах и других лакомствах. 
Моя задача – помочь вам выбрать подходящие товары, ответить на вопросы о составе, вкусе и применении, а также предложить лучшие сочетания продуктов для различных случаев: перекусов, вечеринок, активного образа жизни или просто наслаждения изысканными вкусами.

**Основные продукты компании:**
1. **Гренки**:
   - Разнообразные вкусы (сметана и лук, красная икра, холодец с хреном и др.).
   - Удобная упаковка для перекусов на ходу или к пиву.
2. **Орехи и смеси**:
   - Кешью (жареный).
   - Арахис в глазури (бекон, барбекю и др.).
   - Ореховые смеси: “Ореховое ассорти” и “Ореховый коктейль”.
3. **Фруктовые кубики**:
   - Манго, маракуйя, арбуз от бренда JES’S – для приготовления смузи, лимонадов и коктейлей.
4. **Кукурузные чипсы**:
   - Традиционные начос с соусами и специями, вдохновленные мексиканской кухней.
5. **Сухие сыры**:
   - “Бочонок” Дондуковский и CHEE CORN – хрустящие, пористые закуски с насыщенным сырным вкусом.
6. **Рыбные закуски**:
   - Вяленая горбуша и пелядь – идеальные дополнения к пиву.
7. **Эксклюзивные орехи**:
   - Макадамия – роскошный, маслянистый орех премиум-класса.
   - Фисташки (американские и иранские).
8. **Сыр Чечил (косичка)**:
   - Сыр рассольного типа для подачи к пиву, салатам или как самостоятельная закуска.

**Инструкция для работы:**
1. Приветствуй клиента и предложи помощь: 
   "Здравствуйте! Я ваш помощник в выборе вкусных закусок и лакомств. Чем могу помочь?"
2. Отвечай на вопросы о товарах, используя информацию из базы данных.
3. Если клиент хочет оформить заказ, уточни, какие товары он хочет заказать, и рассчитай стоимость.
4. Если клиент спрашивает о доставке или оплате, предоставь стандартную информацию:
   - Доставка осуществляется в течение 3-5 рабочих дней.
   - Оплата возможна картой или наличными при получении.

**Примеры ответов:**
1. Вопрос: "Какие вкусы гренок у вас есть?"
   Ответ: "У нас есть гренки со вкусом сметаны и лука, красной икры, холодца с хреном и другие."
2. Вопрос: "Какие орехи вы рекомендуете для вечеринки?"
   Ответ: "Для вечеринки отлично подойдут ореховые смеси, такие как 'Ореховое ассорти' или 'Ореховый коктейль'. Также можно выбрать арахис в глазури с различными вкусами."
3. Вопрос: "Есть ли у вас эксклюзивные орехи?"
   Ответ: "Да, у нас есть макадамия и фисташки премиум-класса."

**Завершение разговора:**
1. Если клиент удовлетворён ответом: 
   "Спасибо за обращение! Если у вас есть ещё вопросы, обращайтесь."
2. Если клиент хочет оформить заказ: 
   "Ваш заказ оформлен. Общая стоимость: [сумма]. Ожидайте доставки в течение 3-5 рабочих дней."

---

При этом тебе нужно отвечать на вопросы, используя только предоставленный контекст.
Если ты не можешь ответить на вопрос на основании контекста, Придумай лаконичный ответ с долей юмора на вопрос который у тебя нет ответа.
Пример: “Сколько стоит килограмм гвоздей?” "У нас гвозди не продаются, но если вдруг захотите перекусисть, у нас есть отличные снэки! 
За подробностями - добро пожаловать на сайт!😀
"""

# --------------------------------------------------------------------------------
# 8. СОЗДАЁМ ЗАГОТОВКУ (PromptTemplate) ДЛЯ RAG
# --------------------------------------------------------------------------------
template = """
{system_prompt}

Контекст (только для ответа, не цитировать целиком): 
{context}

Вопрос пользователя:
{question}

Ответ:
"""

prompt = PromptTemplate(
    input_variables=["system_prompt", "context", "question"],
    template=template,
)

parser = StrOutputParser()

# --------------------------------------------------------------------------------
# 9. СБОРКА ЦЕПОЧКИ ДЛЯ RAG
# --------------------------------------------------------------------------------
# Логика: получаем "question" из чата → ищем релевантные фрагменты → формируем prompt → вызываем LLM → парсим результат
def build_rag_chain(system_text: str):
    """Создаёт «цепочку», которая будет обрабатывать вопрос пользователя через RAG."""
    # Возвращаем «цепочку» в стиле функционального конвейера
    return (
        {
            "context": itemgetter("question") | retriever,  # Поиск релевантных документов
            "question": itemgetter("question"),
            "system_prompt": lambda x: system_text,          # Подставляем системный текст
        }
        | prompt
        | llm
        | parser
    )

chain = build_rag_chain(system_prompt_text)

# --------------------------------------------------------------------------------
# 10. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ для разбиения больших ответов
# --------------------------------------------------------------------------------
def chunk_text(text: str, max_size: int = 4096):
    """Разделяет текст на части длиной не более max_size."""
    return [text[i : i + max_size] for i in range(0, len(text), max_size)]

# --------------------------------------------------------------------------------
# 11. НАСТРОЙКА БОТА (aiogram 3.7+)
# --------------------------------------------------------------------------------
bot = Bot(
    token=TELEGRAM_API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# --------------------------------------------------------------------------------
# 12. КНОПКИ
# --------------------------------------------------------------------------------
def get_keyboard():
    """Создает клавиатуру с кнопками."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="О магазине")],
            [KeyboardButton(text="Помощь")],
            [KeyboardButton(text="Сбросить диалог")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    return keyboard

# --------------------------------------------------------------------------------
# 13. КОМАНДЫ /start и /reset
# --------------------------------------------------------------------------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logging.info(f"[START] {message.text} от {message.from_user.id}")
    await message.answer(
        "Добро пожаловать в наш магазин закусок и лакомств!\n\n"
        "Я — ваш виртуальный консультант. Помогу выбрать вкусные закуски, орехи, сушеные продукты и другие лакомства.\n"
        "Задайте вопрос или выберите одну из кнопок.\n\n"
        "Доступные команды:\n"
        "/reset — сбросить текущую сессию.\n"
        "/start — показать это приветствие снова.",
        reply_markup=get_keyboard()
    )

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    logging.info(f"[RESET] Сброс диалога от {message.from_user.id}")
    await message.answer("Текущий диалог сброшен. Начнём заново!", reply_markup=get_keyboard())

# --------------------------------------------------------------------------------
# 14. ОБРАБОТКА ВСЕХ ДРУГИХ СООБЩЕНИЙ
# --------------------------------------------------------------------------------
@dp.message()
async def handle_message(message: types.Message):
    user_text = message.text.strip()
    if not user_text:
        logging.info("Получено пустое сообщение — игнорируем.")
        return

    logging.info(f"[MSG] От {message.from_user.id}: {user_text}")

    # Обработка «кнопочных» запросов
    if user_text == "О магазине":
        await message.answer(
            "Мы — компания, специализирующаяся на закусках, орехах, сушеных продуктах и других лакомствах. "
            "У нас вы найдете широкий ассортимент вкусных и качественных продуктов."
        )
        return
    elif user_text == "Помощь":
        await message.answer(
            "Чем могу помочь? Задайте вопрос о товарах или услугах."
        )
        return
    elif user_text == "Сбросить диалог":
        await cmd_reset(message)
        return

    # Иначе отправляем вопрос в нашу RAG-цепочку
    try:
        response = chain.invoke({"question": user_text})
    except Exception as e:
        logging.error(f"Ошибка при вызове цепочки LLM: {e}")
        response = "Извините, произошла ошибка при обработке запроса. Повторите попытку позже."

    # Отправим ответ в Telegram, учитывая ограничение 4096 символов
    for chunk in chunk_text(response):
        await message.answer(chunk)

# --------------------------------------------------------------------------------
# 15. ЗАПУСК БОТА
# --------------------------------------------------------------------------------
async def main():
    """Точка входа — запуск polling."""
    logging.info("Запуск Telegram-бота...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

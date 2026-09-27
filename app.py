"""
СметаАссистент — ИИ-помощник сметчика.
Не ИИ-сметчик, а ассистент: помогает искать, анализировать, проверять.
"""

import streamlit as st
import pandas as pd

# ===== Настройки страницы =====
st.set_page_config(
    page_title="СметаАссистент",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Стили =====
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a1a;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .result-card {
        background: #f8f9fa;
        border-left: 4px solid #ff6b35;
        padding: 1rem 1.2rem;
        margin: 0.8rem 0;
        border-radius: 6px;
    }
    .result-code {
        font-family: monospace;
        font-weight: 700;
        color: #ff6b35;
        font-size: 1.1rem;
    }
    .result-name {
        font-weight: 600;
        color: #1a1a1a;
        margin: 0.3rem 0;
    }
    .result-detail {
        color: #555;
        font-size: 0.9rem;
    }
</style>
""", unsafe_allow_html=True)

# ===== Заголовок =====
st.markdown('<div class="main-header">🏗️ СметаАссистент</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">ИИ-помощник для поиска, анализа и проверки сметных норм. '
    'Решение всегда остаётся за вами.</div>',
    unsafe_allow_html=True
)

# ===== Функция для запроса к GigaChat =====
def ask_gigachat(question: str) -> str:
    """Отправляет запрос в GigaChat и возвращает ответ."""
    try:
        from gigachat import GigaChat
        credentials = st.secrets["GIGACHAT_CREDENTIALS"]
        with GigaChat(
            credentials=credentials,
            model="GigaChat",
            verify_ssl_certs=False
        ) as client:
            response = client.chat(question)
            return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ Ошибка при обращении к GigaChat: {e}"

# ===== Боковая панель =====
with st.sidebar:
    st.header("⚙️ Настройки")
    
    st.subheader("Источник данных")
    data_source = st.radio(
        "Выберите базу:",
        ["ФСНБ-2022 (федеральная)", "ТСН-2001 (территориальная)", "Локальный кэш"],
        index=0
    )
    
    st.subheader("Регион и период")
    region = st.selectbox(
        "Регион:",
        ["77 — Москва", "78 — Санкт-Петербург", "50 — Московская обл.",
         "23 — Краснодарский край", "66 — Свердловская обл."],
        index=0
    )
    quarter = st.selectbox(
        "Квартал:",
        ["2026 Q3", "2026 Q2", "2026 Q1", "2025 Q4"],
        index=0
    )
    
    st.divider()
    
    st.subheader("🧠 Нейросеть")
    st.info("Модель: **GigaChat** (Сбер)")
    
    st.divider()
    
    st.caption("Версия 0.2 — с GigaChat")
    st.caption("© СметаАссистент")

# ===== Вкладки =====
tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Поиск норм",
    "📊 Анализ ВОР",
    "⚖️ Сравнение норм",
    "💰 Конъюнктурный анализ"
])

# ===== Вкладка 1: Поиск норм с GigaChat =====
with tab1:
    st.subheader("Поиск нормы по описанию работы")
    st.caption("Опишите работу обычными словами — ИИ-ассистент поможет найти подходящие нормы.")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Описание работы:",
            placeholder="Например: кладка перегородок из кирпича толщиной 120 мм",
            label_visibility="collapsed"
        )
    with col2:
        search_btn = st.button("🔍 Найти", use_container_width=True)
    
    if search_btn and query:
        with st.spinner("GigaChat анализирует описание..."):
            prompt = f"""Ты — опытный инженер-сметчик. Пользователь описал работу:
"{query}"

Твоя задача:
1. Определи, к какому виду работ это относится.
2. Предложи 2-3 подходящих кода норм ГЭСН/ФЕР из базы ФСНБ-2022.
3. Кратко объясни, почему ты выбрал именно эти нормы.

Ответь структурировано: код нормы — название — краткое пояснение.
Будь краток и конкретен."""
            
            ai_response = ask_gigachat(prompt)
            
            st.success("💬 Рекомендация GigaChat:")
            st.markdown(ai_response)
            
            st.divider()
            st.info(
                "💡 **Важно:** Это рекомендация нейросети, а не официальные данные. "
                "Проверьте нормы в ФГИС ЦС и примите решение сами. "
                "На следующем этапе мы подключим реальный поиск по базе ФСНБ-2022."
            )
    
    elif search_btn and not query:
        st.warning("Введите описание работы для поиска.")

# ===== Вкладка 2: Анализ ВОР =====
with tab2:
    st.subheader("Анализ ведомости объёмов работ")
    st.caption("Загрузите ВОР в формате Excel — ассистент разберёт позиции и предложит нормы.")
    
    uploaded_file = st.file_uploader(
        "Загрузите файл ВОР (.xlsx):",
        type=["xlsx", "xls"]
    )
    
    if uploaded_file:
        try:
            df = pd.read_excel(uploaded_file)
            st.success(f"Файл загружен: {len(df)} позиций")
            st.dataframe(df.head(10), use_container_width=True)
            
            if st.button("🤖 Проанализировать позиции", use_container_width=True):
                st.info("🔧 Функция в разработке.")
        except Exception as e:
            st.error(f"Ошибка при чтении файла: {e}")
    else:
        st.info("📁 Загрузите файл, чтобы начать анализ.")

# ===== Вкладка 3: Сравнение норм =====
with tab3:
    st.subheader("Сравнение сметных норм")
    st.caption("Введите две нормы — ассистент покажет разницу.")
    
    col1, col2 = st.columns(2)
    with col1:
        norm_a = st.text_input("Норма A:", placeholder="08-02-001-01")
    with col2:
        norm_b = st.text_input("Норма B:", placeholder="08-02-001-02")
    
    if st.button("⚖️ Сравнить", use_container_width=True) and norm_a and norm_b:
        st.info("🔧 Функция в разработке.")

# ===== Вкладка 4: Конъюнктурный анализ =====
with tab4:
    st.subheader("Конъюнктурный анализ материалов")
    st.caption("Проверка цен в ФГИС ЦС и анализ коммерческих предложений.")
    
    st.markdown("**Шаг 1: Проверка в ФГИС ЦС**")
    resource_query = st.text_input(
        "Название ресурса:",
        placeholder="Например: арматура А500С диаметр 12 мм",
        key="ka_query"
    )
    
    if st.button("🔍 Проверить в ФГИС ЦС", use_container_width=True) and resource_query:
        st.info("🔧 Функция в разработке.")
    
    st.divider()
    st.markdown("**Шаг 2: Загрузка коммерческих предложений**")
    kp_files = st.file_uploader(
        "Загрузите КП (PDF, Excel):",
        type=["pdf", "xlsx", "xls"],
        accept_multiple_files=True,
        key="kp_upload"
    )
    
    if kp_files:
        st.success(f"Загружено файлов: {len(kp_files)}")
        st.info("🔧 Функция в разработке.")

# ===== Подвал =====
st.divider()
st.caption(
    "🏗️ СметаАссистент — ИИ-помощник, а не замена специалиста. "
    "Все решения принимает инженер-сметчик."
)
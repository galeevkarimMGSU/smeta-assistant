"""
СметаАссистент — ИИ-помощник сметчика.
Поиск норм в реальной базе ФСНБ-2022.
"""

import streamlit as st
import sqlite3
import os

st.set_page_config(
    page_title="СметаАссистент",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    .highlight {
        background-color: #fff3cd;
        padding: 0 2px;
        border-radius: 2px;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏗️ СметаАссистент</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">ИИ-помощник для поиска, анализа и проверки сметных норм. '
    'Решение всегда остаётся за вами.</div>',
    unsafe_allow_html=True
)

DB_PATH = "fsnb.sqlite"

@st.cache_resource
def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def search_norms(query: str, limit: int = 30):
    """Умный поиск: по коду, по нескольким словам, сортировка по релевантности."""
    conn = get_db_connection()
    if conn is None:
        return None
    cursor = conn.cursor()
    
    query = query.strip()
    if not query:
        return []
    
    # Разбиваем на слова
    words = query.split()
    
    # Проверяем, похож ли запрос на код нормы (содержит цифры и дефисы)
    is_code_like = any(c.isdigit() for c in query) and '-' in query
    
    if is_code_like:
        # Поиск по коду
        cursor.execute("""
            SELECT code, name, unit, unit_name, section, base_type, content_text
            FROM rates
            WHERE code LIKE ?
            LIMIT ?
        """, (f"%{query}%", limit))
    else:
        # Поиск по названию: каждое слово должно встречаться
        conditions = " AND ".join(["name LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]
        params.append(limit)
        cursor.execute(f"""
            SELECT code, name, unit, unit_name, section, base_type, content_text
            FROM rates
            WHERE {conditions}
            LIMIT ?
        """, params)
    
    rows = cursor.fetchall()
    results = []
    for row in rows:
        results.append({
            "code": row[0], "name": row[1], "unit": row[2],
            "unit_name": row[3], "section": row[4],
            "base_type": row[5], "content_text": row[6]
        })
    return results

def get_total_count():
    conn = get_db_connection()
    if conn is None:
        return 0
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM rates")
    return cursor.fetchone()[0]

with st.sidebar:
    st.header("⚙️ Настройки")
    st.subheader("Источник данных")
    st.info("📚 База: **ФСНБ-2022** (образец)")
    total = get_total_count()
    st.caption(f"Всего норм в базе: **{total}**")
    st.divider()
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
    st.caption("Версия 0.4 — умный поиск")
    st.caption("© СметаАссистент")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Поиск норм",
    "📊 Анализ ВОР",
    "⚖️ Сравнение норм",
    "💰 Конъюнктурный анализ"
])

with tab1:
    st.subheader("Поиск нормы по описанию работы")
    st.caption("Введите ключевые слова или код нормы. Поиск работает по нескольким словам.")
    
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Описание работы:",
            placeholder="Например: замена замок, электродвигатель, 01-01-001",
            label_visibility="collapsed"
        )
    with col2:
        search_btn = st.button("🔍 Найти", use_container_width=True)
    
    if search_btn and query:
        with st.spinner("Ищу в базе ФСНБ..."):
            results = search_norms(query)
            
            if results is None:
                st.error("⚠️ База данных не найдена. Убедитесь, что файл fsnb.sqlite находится в папке проекта.")
            elif len(results) == 0:
                st.warning(f"По запросу «{query}» ничего не найдено. Попробуйте другие слова или код.")
            else:
                st.success(f"Найдено норм: **{len(results)}**")
                for r in results:
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-code">{r["code"]}</div>
                        <div class="result-name">{r["name"]}</div>
                        <div class="result-detail">
                            📏 Ед. изм.: {r["unit"]} ({r["unit_name"]}) &nbsp;|&nbsp; 
                            📚 {r["base_type"]}
                        </div>
                        <div class="result-detail" style="margin-top:0.3rem;">
                            {r["section"][:150]}...
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    with st.expander("📋 Показать состав работ"):
                        st.text(r["content_text"])
                st.info("💡 Проверьте состав работ и убедитесь, что норма подходит.")
    elif search_btn and not query:
        st.warning("Введите описание работы для поиска.")
    
    st.divider()
    st.caption("💡 Совет: используйте ключевые слова (например, «лифт», «замок») или код нормы (например, 01-01-001).")

with tab2:
    st.subheader("Анализ ведомости объёмов работ")
    st.caption("Загрузите ВОР в формате Excel — ассистент разберёт позиции.")
    uploaded_file = st.file_uploader("Загрузите файл ВОР (.xlsx):", type=["xlsx", "xls"])
    if uploaded_file:
        try:
            import pandas as pd
            df = pd.read_excel(uploaded_file)
            st.success(f"Файл загружен: {len(df)} позиций")
            st.dataframe(df.head(10), use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка при чтении файла: {e}")
    else:
        st.info("📁 Загрузите файл, чтобы начать анализ.")

with tab3:
    st.subheader("Сравнение сметных норм")
    col1, col2 = st.columns(2)
    with col1:
        norm_a = st.text_input("Норма A:", placeholder="01-01-001-01")
    with col2:
        norm_b = st.text_input("Норма B:", placeholder="01-01-001-02")
    if st.button("⚖️ Сравнить", use_container_width=True) and norm_a and norm_b:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT code, name, content_text FROM rates WHERE code = ?", (norm_a,))
            a = cursor.fetchone()
            cursor.execute("SELECT code, name, content_text FROM rates WHERE code = ?", (norm_b,))
            b = cursor.fetchone()
            if a and b:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**{a[0]}**")
                    st.write(a[1])
                    st.text(a[2])
                with col2:
                    st.markdown(f"**{b[0]}**")
                    st.write(b[1])
                    st.text(b[2])
            else:
                st.warning("Одна или обе нормы не найдены в базе.")

with tab4:
    st.subheader("Конъюнктурный анализ материалов")
    st.markdown("**Шаг 1: Проверка в ФГИС ЦС**")
    resource_query = st.text_input("Название ресурса:", placeholder="Арматура А500С 12 мм", key="ka_query")
    if st.button("🔍 Проверить в ФГИС ЦС", use_container_width=True) and resource_query:
        st.info("🔧 Функция в разработке.")
    st.divider()
    st.markdown("**Шаг 2: Загрузка коммерческих предложений**")
    kp_files = st.file_uploader("Загрузите КП (PDF, Excel):", type=["pdf", "xlsx", "xls"], accept_multiple_files=True, key="kp_upload")
    if kp_files:
        st.success(f"Загружено файлов: {len(kp_files)}")

st.divider()
st.caption("🏗️ СметаАссистент — ИИ-помощник, а не замена специалиста.")
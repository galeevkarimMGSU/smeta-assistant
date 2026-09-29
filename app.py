"""
СметаАссистент — ИИ-помощник сметчика.
Поиск норм в полной базе ФСНБ-2022.
"""

import streamlit as st
import sqlite3
import os
import zipfile

st.set_page_config(
    page_title="СметаАссистент",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1a1a1a; margin-bottom: 0.2rem; }
    .sub-header { font-size: 1rem; color: #666; margin-bottom: 2rem; }
    .result-card {
        background: #ffffff; border: 1px solid #e5e5e5;
        border-left: 4px solid #ff6b35; padding: 1.2rem 1.4rem;
        margin: 0.8rem 0; border-radius: 6px;
    }
    .result-number { color: #999; font-size: 0.85rem; font-weight: 600; }
    .result-code {
        font-family: 'Consolas', monospace; font-weight: 700;
        color: #ff6b35; font-size: 1.15rem; background: #fff5f0;
        padding: 2px 8px; border-radius: 4px; display: inline-block;
    }
    .result-name { font-weight: 600; color: #1a1a1a; margin: 0.5rem 0; font-size: 1.05rem; }
    .result-meta { color: #555; font-size: 0.85rem; margin: 0.3rem 0; }
    .result-section {
        color: #777; font-size: 0.85rem; font-style: italic;
        margin-top: 0.5rem; padding-top: 0.5rem; border-top: 1px dashed #e5e5e5;
    }
    .composition-box {
        background: #f8f9fa; border-radius: 4px; padding: 0.8rem 1rem;
        margin-top: 0.8rem; font-size: 0.9rem; color: #333;
        white-space: pre-line; line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏗️ СметаАссистент</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">ИИ-помощник для поиска, анализа и проверки сметных норм. '
    'Решение всегда остаётся за вами.</div>',
    unsafe_allow_html=True
)

# ===== Автоматическая распаковка базы из ZIP =====
DB_PATH = "fsnb.sqlite"
zip_path = "fsnb.zip"

if os.path.exists(zip_path):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_name in zip_ref.namelist():
            if file_name.endswith('.sqlite'):
                with zip_ref.open(file_name) as source:
                    with open(DB_PATH, 'wb') as target:
                        target.write(source.read())
                break

@st.cache_resource
def get_db_connection():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn

def get_all_base_types():
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT base_type FROM rates WHERE base_type IS NOT NULL ORDER BY base_type")
    return [row[0] for row in cursor.fetchall()]

def get_all_units():
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT unit FROM rates WHERE unit IS NOT NULL ORDER BY unit")
    return [row[0] for row in cursor.fetchall()]

def get_rate_composition(code: str, base_type: str):
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor()
    cursor.execute("""
        SELECT resource_type, resource_code, resource_name, unit, qty_per_unit
        FROM resources
        WHERE work_code = ? AND work_base_type = ?
        ORDER BY resource_type, resource_code
    """, (code, base_type))
    return cursor.fetchall()

def search_norms(query: str, base_types=None, units=None, sort_by="relevance", limit=30):
    conn = get_db_connection()
    if conn is None: return None
    cursor = conn.cursor()
    query = query.strip()
    if not query: return []
    words = query.split()
    is_code_like = any(c.isdigit() for c in query) and '-' in query
    where_parts = []
    params = []
    if is_code_like:
        where_parts.append("code LIKE ?")
        params.append(f"%{query}%")
    else:
        for w in words:
            where_parts.append("name LIKE ?")
            params.append(f"%{w}%")
    if base_types:
        placeholders = ",".join(["?" for _ in base_types])
        where_parts.append(f"base_type IN ({placeholders})")
        params.extend(base_types)
    if units:
        placeholders = ",".join(["?" for _ in units])
        where_parts.append(f"unit IN ({placeholders})")
        params.extend(units)
    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    if sort_by == "code": order_clause = "ORDER BY code"
    elif sort_by == "name": order_clause = "ORDER BY name"
    else: order_clause = "ORDER BY code"
    params.append(limit)
    sql = f"""
        SELECT code, name, unit, unit_name, section, base_type, content_text,
               source_order, source_edition, effective_date
        FROM rates
        WHERE {where_clause}
        {order_clause}
        LIMIT ?
    """
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    results = []
    for row in rows:
        results.append({
            "code": row[0], "name": row[1], "unit": row[2],
            "unit_name": row[3], "section": row[4], "base_type": row[5],
            "content_text": row[6], "source_order": row[7],
            "source_edition": row[8], "effective_date": row[9]
        })
    return results

def export_to_excel(results):
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    wb = Workbook()
    ws = wb.active
    ws.title = "Нормы ФСНБ-2022"

    headers = ["№", "Код нормы", "Наименование", "Ед. изм.", "Тип базы", "Раздел", "Состав работ"]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )

    for col_idx, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    for idx, r in enumerate(results, 1):
        ws.append([
            idx,
            r["code"],
            r["name"],
            f"{r['unit']} ({r['unit_name']})",
            r["base_type"],
            r["section"],
            r["content_text"]
        ])

    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 50
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 40
    ws.column_dimensions['G'].width = 60

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

def get_total_count():
    conn = get_db_connection()
    if conn is None: return 0
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM rates")
    return cursor.fetchone()[0]

with st.sidebar:
    st.header("⚙️ Настройки")
    st.subheader("📚 Источник данных")
    st.info("ФСНБ-2022 (полная база)")
    total = get_total_count()
    st.caption(f"Всего норм: **{total}**")
    st.divider()
    st.subheader("🎯 Фильтры поиска")
    all_base_types = get_all_base_types()
    selected_base_types = st.multiselect(
        "Тип базы:", options=all_base_types, default=[],
        help="Оставьте пустым, чтобы искать по всем типам"
    )
    all_units = get_all_units()
    selected_units = st.multiselect(
        "Единица измерения:", options=all_units, default=[],
        help="Оставьте пустым, чтобы искать по всем единицам"
    )
    sort_by = st.selectbox(
        "Сортировка:", options=["relevance", "code", "name"],
        format_func=lambda x: {"relevance": "По релевантности", "code": "По коду", "name": "По названию"}[x],
        index=0
    )
    result_limit = st.selectbox("Максимум результатов:", options=[10, 30, 50, 100], index=1)
    st.divider()
    st.subheader("📍 Регион и период")
    region = st.selectbox(
        "Регион:",
        ["77 — Москва", "78 — Санкт-Петербург", "50 — Московская обл.",
         "23 — Краснодарский край", "66 — Свердловская обл."],
        index=0
    )
    quarter = st.selectbox("Квартал:", ["2026 Q3", "2026 Q2", "2026 Q1", "2025 Q4"], index=0)
    st.divider()
    st.caption("Версия 1.0 — полная база ФСНБ")
    st.caption("© СметаАссистент")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Поиск норм", "📊 Анализ ВОР", "⚖️ Сравнение норм", "💰 Конъюнктурный анализ"
])

with tab1:
    st.subheader("Поиск нормы по описанию работы")
    st.caption("Введите ключевые слова или код. Используйте фильтры в боковой панели для уточнения.")
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input(
            "Описание работы:",
            placeholder="Например: кирпич, бетон, монтаж, 01-01-001",
            label_visibility="collapsed"
        )
    with col2:
        search_btn = st.button("🔍 Найти", use_container_width=True)
    if search_btn and query:
        with st.spinner("Ищу в базе ФСНБ..."):
            results = search_norms(
                query,
                base_types=selected_base_types if selected_base_types else None,
                units=selected_units if selected_units else None,
                sort_by=sort_by,
                limit=result_limit
            )
            if results is None:
                st.error("⚠️ База данных не найдена.")
            elif len(results) == 0:
                st.warning(f"По запросу «{query}» ничего не найдено.")
            else:
                col_info, col_export = st.columns([3, 1])
                with col_info:
                    st.success(f"Найдено норм: **{len(results)}**")
                with col_export:
                    excel_buffer = export_to_excel(results)
                    st.download_button(
                        label="📥 Скачать в Excel",
                        data=excel_buffer,
                        file_name=f"fsnb_{query.replace(' ', '_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )

                for idx, r in enumerate(results, 1):
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-number">#{idx}</div>
                        <div class="result-code">{r["code"]}</div>
                        <div class="result-name">{r["name"]}</div>
                        <div class="result-meta">
                            📏 <b>{r["unit"]}</b> ({r["unit_name"]}) &nbsp;|&nbsp; 
                            📚 <b>{r["base_type"]}</b> &nbsp;|&nbsp;
                            📅 {r["effective_date"] or "—"}
                        </div>
                        <div class="result-meta">
                            📖 Источник: {r["source_edition"] or r["source_order"] or "—"}
                        </div>
                        <div class="result-section">
                            {r["section"][:200]}...
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    col_a, col_b = st.columns([1, 4])
                    with col_a:
                        if st.button(f"📋 Копировать {r['code']}", key=f"copy_{idx}_{r['code']}"):
                            st.toast(f"Код {r['code']} скопирован!", icon="✅")
                    with st.expander("📋 Состав работ", expanded=False):
                        st.markdown(f'<div class="composition-box">{r["content_text"]}</div>', unsafe_allow_html=True)
                    with st.expander("📊 Расход ресурсов", expanded=False):
                        resources = get_rate_composition(r["code"], r["base_type"])
                        if not resources:
                            st.info("Для этой нормы в базе нет данных о расходе ресурсов.")
                        else:
                            type_names = {"labor": "👷 Трудозатраты", "machines": "🚜 Машины и механизмы", "materials": "📦 Материалы"}
                            for res_type in ["labor", "machines", "materials"]:
                                res_subset = [res for res in resources if res[0] == res_type]
                                if res_subset:
                                    st.markdown(f"**{type_names[res_type]}**")
                                    for _, res_code, res_name, res_unit, qty in res_subset:
                                        st.markdown(f"- `{res_code}` — {res_name} — **{qty:.4f}** {res_unit}")
                                    st.markdown("---")
                st.info("💡 Проверьте состав работ и расход ресурсов.")
    elif search_btn and not query:
        st.warning("Введите описание работы для поиска.")

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
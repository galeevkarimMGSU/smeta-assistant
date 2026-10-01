"""
СметаАссистент — ИИ-помощник сметчика.
Полная база ФСНБ-2022 + FTS5-поиск с bm25-ранжированием.
"""

import streamlit as st
import sqlite3
import os
import zipfile
import re

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
    .result-code {
        font-family: 'Consolas', monospace; font-weight: 700;
        color: #ff6b35; font-size: 1.15rem; background: #fff5f0;
        padding: 2px 8px; border-radius: 4px; display: inline-block;
    }
    .result-name { font-weight: 600; color: #1a1a1a; margin: 0.5rem 0; font-size: 1.05rem; }
    .result-meta { color: #555; font-size: 0.85rem; margin: 0.3rem 0; }
    .composition-box {
        background: #f8f9fa; border-radius: 4px; padding: 0.8rem 1rem;
        margin-top: 0.8rem; font-size: 0.9rem; color: #333;
        white-space: pre-line; line-height: 1.5;
    }
    .detect-box {
        background: #e8f4f8; border-left: 4px solid #2196f3;
        padding: 1rem; border-radius: 6px; margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">🏗️ СметаАссистент</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">ИИ-помощник для поиска, анализа и проверки сметных норм. '
    'Решение всегда остаётся за вами.</div>',
    unsafe_allow_html=True
)

# ===== Автоматическая распаковка базы =====
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
        FROM resources WHERE work_code = ? AND work_base_type = ?
        ORDER BY resource_type, resource_code
    """, (code, base_type))
    return cursor.fetchall()

def clean_html(text):
    if not text: return ""
    text = re.sub(r'<[^>]+>', ' ', str(text))
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# ===== СТОП-СЛОВА =====
STOP_WORDS = {
    'с', 'из', 'на', 'по', 'до', 'в', 'и', 'или', 'для', 'при', 'к', 'от',
    'о', 'об', 'за', 'под', 'над', 'у', 'без', 'через', 'между', 'а', 'но',
    'же', 'бы', 'ли', 'то', 'как', 'так', 'что', 'это', 'её', 'его', 'их',
    'т.д', 'т.п', 'т.е', 'прим'
}

# ===== ОБЩИЕ ГЛАГОЛЫ (только для fallback-поиска) =====
COMMON_VERBS = {
    'демонтаж', 'монтаж', 'разборка', 'устройство', 'установка',
    'прокладка', 'снятие', 'кладка', 'заделка', 'ремонт',
    'разработка', 'погрузка', 'перевозка', 'нанесение',
    'армирование', 'пробивка', 'сверление', 'восстановление',
    'антисептирование', 'штукатурка', 'огрунтовка', 'отбивка',
    'затаривание', 'изготовление', 'сборка', 'разбор', 'укладка',
    'заливка', 'укрепление', 'облицовка', 'утепление', 'изоляция',
    'окраска', 'покраска', 'оклейка', 'обмазка', 'заполнение',
    'перемещение', 'заготовка', 'сбор', 'установление',
    'прочие', 'прочее', 'работы', 'работа'
}

def extract_keywords(text, max_keywords=12, remove_common=False):
    """Извлекает значимые слова из текста."""
    text = clean_html(text).lower()
    text = re.sub(r'[^\w\s\-]', ' ', text)
    words = text.split()
    result = []
    for w in words:
        if w in STOP_WORDS: continue
        if len(w) < 3: continue
        if remove_common and w in COMMON_VERBS: continue
        if w not in result:
            result.append(w)
    return result[:max_keywords]

def stem(word):
    """Грубая основа слова (убирает последние 1-2 символа)."""
    if len(word) <= 4: return word
    return word[:max(len(word) - 2, 4)]

def escape_fts(word):
    """Убирает спецсимволы FTS5."""
    return re.sub(r'["()*:^\-]', '', word)

def is_material(work_name, unit_val):
    """Определяет, является ли строка материалом."""
    work_lower = work_name.lower()

    action_verbs = [
        'разборка', 'демонтаж', 'монтаж', 'устройство', 'установка',
        'прокладка', 'снятие', 'кладка', 'заделка', 'ремонт',
        'разработка', 'погрузка', 'перевозка', 'нанесение',
        'армирование', 'пробивка', 'сверление', 'восстановление',
        'антисептирование', 'штукатурка', 'огрунтовка', 'отбивка',
        'затаривание', 'изготовление', 'сборка', 'разбор', 'укладка',
        'заливка', 'укрепление', 'облицовка', 'утепление', 'изоляция',
        'окраска', 'покраска', 'оклейка', 'обмазка', 'заполнение',
        'перемещение', 'заготовка', 'сбор', 'установление'
    ]
    if any(v in work_lower for v in action_verbs):
        return False

    material_keywords = [
        'лист', 'сетка', 'смесь', 'грунтовка', 'сверло',
        'краска', 'лак', 'эмаль', 'клей', 'мастика', 'герметик', 'пена',
        'профиль', 'уголок', 'труба', 'кабель', 'провод', 'арматура',
        'бетон', 'раствор', 'цемент', 'песок', 'щебень', 'кирпич',
        'блок', 'плита', 'панель', 'утеплитель',
        'мембрана', 'плёнка', 'пленка', 'саморез', 'дюбель', 'анкер',
        'болт', 'гайка', 'шайба', 'скоба', 'хомут', 'крепёж', 'крепеж',
        'кронштейн', 'подоконник', 'отлив', 'наличник', 'плинтус',
        'плитка', 'керамогранит', 'ламинат', 'линолеум', 'паркет',
        'обои', 'шпаклёвка', 'шпаклевка', 'электрод', 'проволока',
        'лента', 'скотч', 'гипсокартон', 'гкл', 'гвл', 'фанера',
        'герб', 'табло', 'светильник', 'лампа', 'розетка', 'выключатель'
    ]
    if any(mk in work_lower for mk in material_keywords):
        return True
    return False

def build_fts_query(stems, operator="AND"):
    """Строит FTS5-запрос из стемов."""
    parts = [f'"{s}"*' for s in stems if s]
    if not parts:
        return None
    return f" {operator} ".join(parts)

def format_rows(rows):
    return [{
        "code": r[0], "name": r[1], "unit": r[2], "unit_name": r[3],
        "section": r[4], "base_type": r[5], "content_text": r[6],
        "source_order": r[7], "source_edition": r[8], "effective_date": r[9]
    } for r in rows]

def search_norms_fts(query: str, unit_val: str = None, limit=3):
    """
    Умный FTS5-поиск с bm25-ранжированием.
    Стратегия:
      1. AND всех значимых стемов — максимальная точность.
      2. AND топ-3 значимых стемов.
      3. AND топ-2 значимых стемов.
      4. AND всех стемов (с общими глаголами).
      5. OR всех стемов (fallback, но с bm25).
    """
    all_keywords = extract_keywords(query, max_keywords=15, remove_common=False)
    if not all_keywords:
        return []

    # Все стемы
    stems_all = []
    for kw in all_keywords:
        s = escape_fts(stem(kw))
        if len(s) >= 3 and s not in stems_all:
            stems_all.append(s)

    # Стемы без общих глаголов
    specific_keywords = extract_keywords(query, max_keywords=15, remove_common=True)
    stems_specific = []
    for kw in specific_keywords:
        s = escape_fts(stem(kw))
        if len(s) >= 3 and s not in stems_specific:
            stems_specific.append(s)

    if not stems_all and not stems_specific:
        return []

    conn = get_db_connection()
    if conn is None:
        return []
    cursor = conn.cursor()

    # Стратегии по убыванию точности
    strategies = []
    if len(stems_specific) >= 2:
        strategies.append(build_fts_query(stems_specific, "AND"))
    if len(stems_specific) >= 3:
        strategies.append(build_fts_query(stems_specific[:3], "AND"))
    if len(stems_specific) >= 2:
        strategies.append(build_fts_query(stems_specific[:2], "AND"))
    if len(stems_all) >= 2:
        strategies.append(build_fts_query(stems_all, "AND"))
    if stems_specific:
        strategies.append(build_fts_query(stems_specific, "OR"))
    if stems_all:
        strategies.append(build_fts_query(stems_all, "OR"))

    for fts_q in strategies:
        if not fts_q:
            continue
        try:
            cursor.execute("""
                SELECT r.code, r.name, r.unit, r.unit_name, r.section, r.base_type,
                       r.content_text, r.source_order, r.source_edition, r.effective_date
                FROM rates_fts
                JOIN rates r ON r.rowid = rates_fts.rowid
                WHERE rates_fts MATCH ?
                ORDER BY bm25(rates_fts)
                LIMIT 100
            """, (fts_q,))
            rows = cursor.fetchall()
            if rows:
                # Python-переранжирование
                scored = []
                for row in rows:
                    name_low = row[1].lower()
                    matched = sum(1 for s in stems_all if s in name_low)

                    unit_bonus = 0
                    if unit_val:
                        uv = unit_val.lower().strip()
                        row_unit = (row[2] or "").lower()
                        if uv and row_unit and (uv in row_unit or row_unit in uv):
                            unit_bonus = 20

                    score = matched * 10 + unit_bonus
                    scored.append((score, row))

                scored.sort(key=lambda x: -x[0])
                return format_rows([r for _, r in scored[:limit]])
        except Exception:
            continue

    return []

def search_norms(query: str, base_types=None, units=None, sort_by="relevance", limit=30):
    """Простой поиск (для вкладки «Поиск норм»)."""
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
        FROM rates WHERE {where_clause} {order_clause} LIMIT ?
    """
    cursor.execute(sql, params)
    return format_rows(cursor.fetchall())

def export_to_excel(results):
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = "Нормы ФСНБ-2022"
    headers = ["№", "Код нормы", "Наименование", "Ед. изм.", "Тип базы", "Раздел", "Состав работ"]
    ws.append(headers)
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font; cell.fill = header_fill
    for idx, r in enumerate(results, 1):
        ws.append([idx, r["code"], r["name"], f"{r['unit']} ({r['unit_name']})",
                   r["base_type"], r["section"], r["content_text"]])
    ws.column_dimensions['A'].width = 5
    ws.column_dimensions['B'].width = 18
    ws.column_dimensions['C'].width = 50
    ws.column_dimensions['D'].width = 15
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 40
    ws.column_dimensions['G'].width = 60
    buf = io.BytesIO(); wb.save(buf); buf.seek(0); return buf

def export_vor_to_excel(results_df):
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "ВОР с нормами"
    headers = list(results_df.columns); ws.append(headers)
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font; cell.fill = header_fill
    for _, row in results_df.iterrows(): ws.append(list(row))
    for c in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 30
    buf = io.BytesIO(); wb.save(buf); buf.seek(0); return buf

def get_total_count():
    conn = get_db_connection()
    if conn is None: return 0
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM rates")
    return cursor.fetchone()[0]

def detect_vor_structure(file_buffer):
    import pandas as pd
    file_buffer.seek(0)
    df_raw = pd.read_excel(file_buffer, header=None, nrows=30)
    header_row = name_col = unit_col = qty_col = None
    name_kw = ["наименование", "работа", "описание", "вид работ"]
    unit_kw = ["ед", "единица", "изм"]
    qty_kw = ["кол", "количество", "объём", "объем", "кол-во"]
    for i, row in df_raw.iterrows():
        rv = [str(v).lower().strip() if pd.notna(v) else "" for v in row]
        has_n = any(any(k in v for k in name_kw) for v in rv)
        has_u = any(any(k in v for k in unit_kw) for v in rv)
        has_q = any(any(k in v for k in qty_kw) for v in rv)
        if has_n and (has_u or has_q):
            header_row = i
            for j, v in enumerate(rv):
                if any(k in v for k in name_kw) and name_col is None: name_col = j
                if any(k in v for k in unit_kw) and unit_col is None: unit_col = j
                if any(k in v for k in qty_kw) and qty_col is None: qty_col = j
            break
    return {
        "header_row": header_row if header_row is not None else 0,
        "name_col": name_col if name_col is not None else 1,
        "unit_col": unit_col if unit_col is not None else 2,
        "qty_col": qty_col if qty_col is not None else 3,
        "found": header_row is not None
    }

# ===== БОКОВАЯ ПАНЕЛЬ =====
with st.sidebar:
    st.header("⚙️ Настройки")
    st.subheader("📚 Источник данных")
    st.info("ФСНБ-2022 (полная база)")
    st.caption(f"Всего норм: **{get_total_count()}**")
    st.divider()
    st.subheader("🎯 Фильтры поиска")
    all_base_types = get_all_base_types()
    selected_base_types = st.multiselect("Тип базы:", options=all_base_types, default=[])
    all_units = get_all_units()
    selected_units = st.multiselect("Единица измерения:", options=all_units, default=[])
    sort_by = st.selectbox("Сортировка:", options=["relevance", "code", "name"],
        format_func=lambda x: {"relevance": "По релевантности", "code": "По коду", "name": "По названию"}[x], index=0)
    result_limit = st.selectbox("Максимум результатов:", options=[10, 30, 50, 100], index=1)
    st.divider()
    st.caption("Версия 1.5 — bm25-поиск")
    st.caption("© СметаАссистент")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 Поиск норм", "📊 Анализ ВОР", "⚖️ Сравнение норм", "💰 Конъюнктурный анализ"
])

# ===== ВКЛАДКА 1 =====
with tab1:
    st.subheader("Поиск нормы по описанию работы")
    col1, col2 = st.columns([4, 1])
    with col1:
        query = st.text_input("Описание работы:", placeholder="Например: светильник, штукатурка", label_visibility="collapsed")
    with col2:
        search_btn = st.button("🔍 Найти", use_container_width=True)

    if search_btn and query:
        with st.spinner("Ищу в базе ФСНБ..."):
            results = search_norms(query, base_types=selected_base_types if selected_base_types else None,
                units=selected_units if selected_units else None, sort_by=sort_by, limit=result_limit)
            if results is None:
                st.error("⚠️ База данных не найдена.")
            elif len(results) == 0:
                st.warning(f"По запросу «{query}» ничего не найдено.")
            else:
                col_info, col_export = st.columns([3, 1])
                with col_info: st.success(f"Найдено: **{len(results)}**")
                with col_export:
                    st.download_button("📥 Excel", data=export_to_excel(results),
                        file_name=f"fsnb_{query.replace(' ','_')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                for r in results:
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-code">{r["code"]}</div>
                        <div class="result-name">{r["name"]}</div>
                        <div class="result-meta">📏 <b>{r["unit"]}</b> ({r["unit_name"]}) | 📚 {r["base_type"]}</div>
                    </div>
                    """, unsafe_allow_html=True)

# ===== ВКЛАДКА 2: ВОР =====
with tab2:
    st.subheader("Анализ ВОР")
    st.caption("Загрузите ВОР — ассистент подберёт нормы через FTS5+bm25.")

    uploaded_file = st.file_uploader("Файл ВОР (.xlsx, .xls):", type=["xlsx", "xls"])

    if uploaded_file:
        import pandas as pd
        try:
            detected = detect_vor_structure(uploaded_file)
            if detected["found"]:
                st.markdown(f"""
                <div class="detect-box">
                    ✅ Шапка: строка <b>{detected["header_row"] + 1}</b> |
                    📝 Наименование: <b>{chr(65 + detected["name_col"])}</b> |
                    📏 Ед. изм.: <b>{chr(65 + detected["unit_col"])}</b> |
                    🔢 Объём: <b>{chr(65 + detected["qty_col"])}</b>
                </div>
                """, unsafe_allow_html=True)

            with st.expander("🔧 Настройки чтения", expanded=not detected["found"]):
                colA, colB = st.columns(2)
                with colA:
                    hr = st.number_input("Строка с шапкой:", 0, 50, detected["header_row"], 1)
                with colB:
                    nc = st.number_input("Столбец наименования:", 0, 30, detected["name_col"], 1)
                colC, colD = st.columns(2)
                with colC:
                    uc = st.number_input("Столбец ед. изм.:", 0, 30, detected["unit_col"], 1)
                with colD:
                    qc = st.number_input("Столбец объёма:", 0, 30, detected["qty_col"], 1)
                include_sub = st.checkbox("Включать подпункты (7.1, 8.1)", value=False)

            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, header=hr)
            st.dataframe(df.head(10), use_container_width=True)

            if st.button("🤖 Подобрать нормы", use_container_width=True):
                results_data = []
                counter = 0
                progress = st.progress(0)

                for idx, row in df.iterrows():
                    try:
                        work_name = clean_html(row.iloc[nc]) if pd.notna(row.iloc[nc]) else ""
                    except: continue
                    if not work_name or len(work_name) < 5: continue
                    if work_name.lower().startswith(("раздел", "итого", "всего", "№ п/п", "п/п")): continue
                    if work_name.replace(".", "").replace(",", "").replace(" ", "").isdigit(): continue

                    row_num = ""
                    try: row_num = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                    except: pass

                    is_sub = "." in row_num and row_num.split(".")[0].isdigit()
                    if is_sub and not include_sub: continue

                    counter += 1
                    try: unit_val = str(row.iloc[uc]).strip() if pd.notna(row.iloc[uc]) else "—"
                    except: unit_val = "—"
                    try: qty_val = str(row.iloc[qc]).strip() if pd.notna(row.iloc[qc]) else "—"
                    except: qty_val = "—"

                    res = {"№": counter, "Работа из ВОР": work_name[:200],
                           "Ед. изм. (ВОР)": unit_val, "Объём": qty_val,
                           "Код нормы": "", "Наименование нормы": "", "Тип базы": "", "Код вручную": ""}

                    if is_material(work_name, unit_val):
                        res["Код нормы"] = "📦 Материал"
                        res["Наименование нормы"] = "Норма не требуется"
                        res["Тип базы"] = "—"
                    else:
                        matches = search_norms_fts(work_name, unit_val=unit_val, limit=3)
                        if matches:
                            m = matches[0]
                            res["Код нормы"] = m["code"]
                            res["Наименование нормы"] = m["name"][:150]
                            res["Тип базы"] = m["base_type"]
                        else:
                            res["Код нормы"] = "❌ не найдено"
                            res["Наименование нормы"] = "—"
                            res["Тип базы"] = "—"
                    results_data.append(res)
                    if len(df) > 0: progress.progress(min((idx+1)/len(df), 1.0))

                progress.empty()
                if results_data:
                    results_df = pd.DataFrame(results_data)
                    st.dataframe(results_df, use_container_width=True, height=500)
                    st.download_button("📥 Скачать Excel", data=export_vor_to_excel(results_df),
                        file_name="ВОР_с_нормами.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                    total = len(results_data)
                    mats = sum(1 for r in results_data if r["Код нормы"] == "📦 Материал")
                    found = sum(1 for r in results_data if r["Код нормы"] and r["Код нормы"] not in ["📦 Материал", "❌ не найдено"])
                    nf = sum(1 for r in results_data if r["Код нормы"] == "❌ не найдено")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Всего", total); c2.metric("✅ Найдено", found)
                    c3.metric("📦 Материалов", mats); c4.metric("❌ Не найдено", nf)
                    if total > 0: st.info(f"📊 Обработано: {round((found+mats)/total*100)}%")
        except Exception as e:
            st.error(f"Ошибка: {e}")
    else:
        st.info("📁 Загрузите файл ВОР.")

# ===== ВКЛАДКА 3 =====
with tab3:
    st.subheader("Сравнение норм")
    col1, col2 = st.columns(2)
    with col1: na = st.text_input("Норма A:", placeholder="01-01-001-01")
    with col2: nb = st.text_input("Норма B:", placeholder="01-01-001-02")
    if st.button("⚖️ Сравнить", use_container_width=True) and na and nb:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT code, name, content_text FROM rates WHERE code = ?", (na,))
            a = cur.fetchone()
            cur.execute("SELECT code, name, content_text FROM rates WHERE code = ?", (nb,))
            b = cur.fetchone()
            if a and b:
                c1, c2 = st.columns(2)
                with c1: st.markdown(f"**{a[0]}**"); st.write(a[1]); st.text(a[2])
                with c2: st.markdown(f"**{b[0]}**"); st.write(b[1]); st.text(b[2])
            else: st.warning("Нормы не найдены.")

# ===== ВКЛАДКА 4 =====
with tab4:
    st.subheader("Конъюнктурный анализ")
    rq = st.text_input("Название ресурса:", key="ka_q")
    if st.button("🔍 Проверить", use_container_width=True) and rq:
        st.info("🔧 В разработке.")

st.divider()
st.caption("🏗️ СметаАссистент — ИИ-помощник, а не замена специалиста.")
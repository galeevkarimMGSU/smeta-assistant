"""
СметаАссистент — ИИ-помощник сметчика.
Полная база ФСНБ-2022 + FTS5-поиск + распределение по разделам.
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
    .section-header {
        background: #ff6b35; color: white; padding: 0.6rem 1rem;
        border-radius: 6px; margin: 1.5rem 0 0.5rem 0;
        font-weight: 700; font-size: 1.05rem;
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

# ===== РАЗДЕЛЫ =====
SECTIONS_ORDER = [
    "1. Подготовка территории строительства",
    "2. Подземная часть",
    "3. Надземная часть",
    "4. Инженерные системы",
    "5. Благоустройство и озеленение",
    "6. Наружные сети",
    "7. Прочие работы",
]

# Ключевые слова для определения раздела (по названию работы)
SECTION_KEYWORDS = {
    "1. Подготовка территории строительства": [
        'вырубка', 'кустарник', 'деревьев', 'геодезическ', 'вынос в натуру',
        'переустройство', 'вынос кабельн', 'вынос водосток', 'снос',
        'подготовка территор', 'демонтаж наружн', 'посадка здания',
    ],
    "2. Подземная часть": [
        'земляны', 'разработка грунт', 'обратная засыпка', 'грунт',
        'фундамент', 'подвал', 'дренаж', 'пристенн', 'гидроизоляц',
        'бетонная подготовк', 'свая', 'свайн', 'ростверк', 'цоколь подземн',
        'стены подземн', 'подземн', 'котлован', 'основание под фундамент',
    ],
    "3. Надземная часть": [
        'кладка', 'кирпич', 'стен', 'перегородк', 'перекрыт', 'колонн',
        'балок', 'кровл', 'потолк', 'пол', 'стяжк', 'штукатур',
        'облицовк', 'окраск', 'отделк', 'двер', 'окн', 'лестниц',
        'бетон', 'железобетон', 'монолитн', 'каркас', 'фахверк',
        'фасад', 'витраж', 'остеклен', 'навесн', 'панел', 'блок',
        'армирован', 'опалубк', 'мусоропровод', 'входн', 'лоджи',
        'пробивк', 'сверлен', 'борозд', 'отверст', 'лесов',
    ],
    "4. Инженерные системы": [
        'отоплен', 'вентиляц', 'кондициониров', 'водопровод', 'канализац',
        'электроснабж', 'электроосвещ', 'электрооборуд', 'слаботочн',
        'лифт', 'противодымн', 'пожаротушен', 'пожарн', 'сигнализац',
        'диспетчеризац', 'асу', 'скуд', 'видеонаблюден', 'оздс',
        'водомерн', 'итп', 'теплоснабж', 'радиофикац', 'телефонизац',
        'телевиден', 'аскуэ', 'соуэ', 'дератизац',
    ],
    "5. Благоустройство и озеленение": [
        'благоустройств', 'озеленен', 'озелен', 'тротуар', 'газон',
        'дорожк', 'площадк', 'бортов', 'брусчатк', 'асфальт',
        'тактильн', 'резинов', 'крошк', 'посадка дерев', 'посадка кустар',
        'вертикальн планировк', 'проезд', 'автостоянк', 'мусоросборник',
        'мал.архитект', 'маф',
    ],
    "6. Наружные сети": [
        'наружн', 'сети', 'водоотведен', 'водосток', 'кабельн канализ',
        'наружн освещен', 'диспетчеризац наружн', 'прокладка',
    ],
}

def get_section_by_keywords(work_name):
    """Определяет раздел по ключевым словам в названии."""
    if not work_name: return None
    name_lower = work_name.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return section
    return None

def get_section_by_code(code):
    """Определяет раздел по коду нормы."""
    if not code or len(code) < 2: return None
    try:
        prefix = int(code[:2])
    except:
        return None

    if prefix in [1, 2, 3, 4, 5]:
        return "2. Подземная часть"
    if prefix == 49:
        return "2. Подземная часть"
    if prefix in [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 46, 47]:
        return "3. Надземная часть"
    if prefix in [18, 19, 20]:
        return "4. Инженерные системы"
    if prefix in [51, 52, 53]:
        return "3. Надземная часть"
    if prefix in [56, 57, 63, 65, 67, 69]:
        return "3. Надземная часть"
    return None

def define_section(work_name, rate_code=None):
    """
    Определяет раздел для работы.
    Приоритет: ключевые слова названия → код нормы → Прочие работы.
    """
    section = get_section_by_keywords(work_name)
    if section:
        return section
    if rate_code:
        section = get_section_by_code(rate_code)
        if section:
            return section
    return "7. Прочие работы"

# ===== СТОП-СЛОВА =====
STOP_WORDS = {
    'с', 'из', 'на', 'по', 'до', 'в', 'и', 'или', 'для', 'при', 'к', 'от',
    'о', 'об', 'за', 'под', 'над', 'у', 'без', 'через', 'между', 'а', 'но',
    'же', 'бы', 'ли', 'то', 'как', 'так', 'что', 'это', 'её', 'его', 'их',
    'т.д', 'т.п', 'т.е', 'прим'
}

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
    if len(word) <= 4: return word
    return word[:max(len(word) - 2, 4)]

def escape_fts(word):
    return re.sub(r'["()*:^\-]', '', word)

def is_material(work_name, unit_val):
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
    parts = [f'"{s}"*' for s in stems if s]
    if not parts: return None
    return f" {operator} ".join(parts)

def format_rows(rows):
    return [{
        "code": r[0], "name": r[1], "unit": r[2], "unit_name": r[3],
        "section": r[4], "base_type": r[5], "content_text": r[6],
        "source_order": r[7], "source_edition": r[8], "effective_date": r[9]
    } for r in rows]

def search_norms_fts(query: str, unit_val: str = None, limit=3):
    all_keywords = extract_keywords(query, max_keywords=15, remove_common=False)
    if not all_keywords: return []

    stems_all = []
    for kw in all_keywords:
        s = escape_fts(stem(kw))
        if len(s) >= 3 and s not in stems_all:
            stems_all.append(s)

    specific_keywords = extract_keywords(query, max_keywords=15, remove_common=True)
    stems_specific = []
    for kw in specific_keywords:
        s = escape_fts(stem(kw))
        if len(s) >= 3 and s not in stems_specific:
            stems_specific.append(s)

    if not stems_all and not stems_specific: return []

    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor()

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
        if not fts_q: continue
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
    wb = Workbook(); ws = wb.active; ws.title = "Нормы ФСНБ-2022"
    headers = ["№", "Код нормы", "Наименование", "Ед. изм.", "Тип базы", "Раздел", "Состав работ"]
    ws.append(headers)
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c); cell.font = hf; cell.fill = hfill
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
    """Экспорт ВОР с группировкой по разделам — каждый раздел отдельным листом."""
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    # Первый лист — сводка
    ws_summary = wb.active
    ws_summary.title = "Сводка"

    # Группируем
    grouped = {}
    for _, row in results_df.iterrows():
        section = row["Раздел"]
        grouped.setdefault(section, []).append(row)

    # Сводка
    ws_summary.append(["Раздел", "Количество работ"])
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c in [1, 2]:
        cell = ws_summary.cell(row=1, column=c); cell.font = hf; cell.fill = hfill

    for section in SECTIONS_ORDER:
        if section in grouped:
            ws_summary.append([section, len(grouped[section])])
    ws_summary.column_dimensions['A'].width = 50
    ws_summary.column_dimensions['B'].width = 20

    # Отдельный лист для каждого раздела
    for section in SECTIONS_ORDER:
        if section not in grouped: continue
        # Имя листа — не длиннее 31 символа
        sheet_name = section[:31].replace("/", "-").replace("\\", "-").replace("*", "").replace("?", "").replace("[", "").replace("]", "")
        ws = wb.create_sheet(title=sheet_name)

        headers = list(results_df.columns)
        ws.append(headers)
        for c, _ in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c); cell.font = hf; cell.fill = hfill

        for row in grouped[section]:
            ws.append(list(row))

        for c in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(c)].width = 25

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
    st.caption("Версия 1.6 — разделы")
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
        with st.spinner("Ищу..."):
            results = search_norms(query, base_types=selected_base_types if selected_base_types else None,
                units=selected_units if selected_units else None, sort_by=sort_by, limit=result_limit)
            if results is None:
                st.error("⚠️ База данных не найдена.")
            elif len(results) == 0:
                st.warning(f"По запросу «{query}» ничего не найдено.")
            else:
                st.success(f"Найдено: **{len(results)}**")
                for r in results:
                    section = define_section(r["name"], r["code"])
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-code">{r["code"]}</div>
                        <div class="result-name">{r["name"]}</div>
                        <div class="result-meta">📏 <b>{r["unit"]}</b> ({r["unit_name"]}) | 📚 {r["base_type"]} | 📂 <b>{section}</b></div>
                    </div>
                    """, unsafe_allow_html=True)

# ===== ВКЛАДКА 2: ВОР =====
with tab2:
    st.subheader("Анализ ВОР с распределением по разделам")
    st.caption("Загрузите ВОР — ассистент подберёт нормы и распределит их по разделам.")

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

            if st.button("🤖 Подобрать нормы и распределить по разделам", use_container_width=True):
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
                           "Код нормы": "", "Наименование нормы": "", "Тип базы": "",
                           "Раздел": "", "Код вручную": ""}

                    rate_code = None

                    if is_material(work_name, unit_val):
                        res["Код нормы"] = "📦 Материал"
                        res["Наименование нормы"] = "Норма не требуется"
                        res["Тип базы"] = "—"
                    else:
                        matches = search_norms_fts(work_name, unit_val=unit_val, limit=3)
                        if matches:
                            m = matches[0]
                            rate_code = m["code"]
                            res["Код нормы"] = m["code"]
                            res["Наименование нормы"] = m["name"][:150]
                            res["Тип базы"] = m["base_type"]
                        else:
                            res["Код нормы"] = "❌ не найдено"
                            res["Наименование нормы"] = "—"
                            res["Тип базы"] = "—"

                    # Определяем раздел
                    res["Раздел"] = define_section(work_name, rate_code)

                    results_data.append(res)
                    if len(df) > 0: progress.progress(min((idx+1)/len(df), 1.0))

                progress.empty()

                if results_data:
                    results_df = pd.DataFrame(results_data)

                    # Сортировка по разделам
                    section_order = {s: i for i, s in enumerate(SECTIONS_ORDER)}
                    results_df["_sort"] = results_df["Раздел"].map(section_order).fillna(99)
                    results_df = results_df.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)

                    # Сводка по разделам
                    st.markdown("### 📊 Сводка по разделам")
                    section_counts = results_df.groupby("Раздел").size().to_dict()

                    cols = st.columns(3)
                    col_idx = 0
                    for section in SECTIONS_ORDER:
                        if section in section_counts:
                            with cols[col_idx % 3]:
                                st.metric(section[:30], f"{section_counts[section]} работ")
                            col_idx += 1

                    # Таблица результатов
                    st.markdown("### 🎯 Результаты")
                    st.dataframe(results_df, use_container_width=True, height=500)

                    # Экспорт
                    st.download_button("📥 Скачать Excel (с группировкой по разделам)",
                        data=export_vor_to_excel(results_df),
                        file_name="ВОР_с_разделами.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)

                    # Статистика
                    total = len(results_data)
                    mats = sum(1 for r in results_data if r["Код нормы"] == "📦 Материал")
                    found = sum(1 for r in results_data if r["Код нормы"] and r["Код нормы"] not in ["📦 Материал", "❌ не найдено"])
                    nf = sum(1 for r in results_data if r["Код нормы"] == "❌ не найдено")

                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Всего", total); c2.metric("✅ Найдено", found)
                    c3.metric("📦 Материалов", mats); c4.metric("❌ Не найдено", nf)
                    if total > 0:
                        st.info(f"📊 Обработано: {round((found+mats)/total*100)}%")

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
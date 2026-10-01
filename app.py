"""
СметаАссистент — ИИ-помощник сметчика.
ФСНБ-2022 + ВОР + сравнение смет + проверка на ошибки.
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
    .error-critical { background: #ffcdd2; padding: 4px 8px; border-radius: 4px; color: #b71c1c; font-weight: 600; }
    .error-warning { background: #fff9c4; padding: 4px 8px; border-radius: 4px; color: #f57f17; font-weight: 600; }
    .error-info { background: #c8e6c9; padding: 4px 8px; border-radius: 4px; color: #1b5e20; font-weight: 600; }
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
    if not work_name: return None
    name_lower = work_name.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower: return section
    return None

def get_section_by_code(code):
    if not code or len(code) < 2: return None
    try: prefix = int(code[:2])
    except: return None
    if prefix in [1, 2, 3, 4, 5, 49]: return "2. Подземная часть"
    if prefix in [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 46, 47]: return "3. Надземная часть"
    if prefix in [18, 19, 20]: return "4. Инженерные системы"
    if prefix in [51, 52, 53, 56, 57, 63, 65, 67, 69]: return "3. Надземная часть"
    return None

def define_section(work_name, rate_code=None):
    section = get_section_by_keywords(work_name)
    if section: return section
    if rate_code:
        section = get_section_by_code(rate_code)
        if section: return section
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
        if w not in result: result.append(w)
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
    if any(v in work_lower for v in action_verbs): return False
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
    if any(mk in work_lower for mk in material_keywords): return True
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
        if len(s) >= 3 and s not in stems_all: stems_all.append(s)
    specific_keywords = extract_keywords(query, max_keywords=15, remove_common=True)
    stems_specific = []
    for kw in specific_keywords:
        s = escape_fts(stem(kw))
        if len(s) >= 3 and s not in stems_specific: stems_specific.append(s)
    if not stems_all and not stems_specific: return []
    conn = get_db_connection()
    if conn is None: return []
    cursor = conn.cursor()
    strategies = []
    if len(stems_specific) >= 2: strategies.append(build_fts_query(stems_specific, "AND"))
    if len(stems_specific) >= 3: strategies.append(build_fts_query(stems_specific[:3], "AND"))
    if len(stems_specific) >= 2: strategies.append(build_fts_query(stems_specific[:2], "AND"))
    if len(stems_all) >= 2: strategies.append(build_fts_query(stems_all, "AND"))
    if stems_specific: strategies.append(build_fts_query(stems_specific, "OR"))
    if stems_all: strategies.append(build_fts_query(stems_all, "OR"))
    for fts_q in strategies:
        if not fts_q: continue
        try:
            cursor.execute("""
                SELECT r.code, r.name, r.unit, r.unit_name, r.section, r.base_type,
                       r.content_text, r.source_order, r.source_edition, r.effective_date
                FROM rates_fts JOIN rates r ON r.rowid = rates_fts.rowid
                WHERE rates_fts MATCH ? ORDER BY bm25(rates_fts) LIMIT 100
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
                        if uv and row_unit and (uv in row_unit or row_unit in uv): unit_bonus = 20
                    score = matched * 10 + unit_bonus
                    scored.append((score, row))
                scored.sort(key=lambda x: -x[0])
                return format_rows([r for _, r in scored[:limit]])
        except Exception: continue
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
        where_parts.append("code LIKE ?"); params.append(f"%{query}%")
    else:
        for w in words:
            where_parts.append("name LIKE ?"); params.append(f"%{w}%")
    if base_types:
        ph = ",".join(["?" for _ in base_types]); where_parts.append(f"base_type IN ({ph})"); params.extend(base_types)
    if units:
        ph = ",".join(["?" for _ in units]); where_parts.append(f"unit IN ({ph})"); params.extend(units)
    where_clause = " AND ".join(where_parts) if where_parts else "1=1"
    if sort_by == "code": order_clause = "ORDER BY code"
    elif sort_by == "name": order_clause = "ORDER BY name"
    else: order_clause = "ORDER BY code"
    params.append(limit)
    cursor.execute(f"""
        SELECT code, name, unit, unit_name, section, base_type, content_text,
               source_order, source_edition, effective_date
        FROM rates WHERE {where_clause} {order_clause} LIMIT ?
    """, params)
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
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws_summary = wb.active; ws_summary.title = "Сводка"
    grouped = {}
    for _, row in results_df.iterrows():
        grouped.setdefault(row["Раздел"], []).append(row)
    ws_summary.append(["Раздел", "Количество работ"])
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c in [1, 2]:
        cell = ws_summary.cell(row=1, column=c); cell.font = hf; cell.fill = hfill
    for section in SECTIONS_ORDER:
        if section in grouped: ws_summary.append([section, len(grouped[section])])
    ws_summary.column_dimensions['A'].width = 50
    ws_summary.column_dimensions['B'].width = 20
    for section in SECTIONS_ORDER:
        if section not in grouped: continue
        sheet_name = section[:31].replace("/", "-").replace("\\", "-").replace("*", "").replace("?", "").replace("[", "").replace("]", "")
        ws = wb.create_sheet(title=sheet_name)
        headers = list(results_df.columns); ws.append(headers)
        for c, _ in enumerate(headers, 1):
            cell = ws.cell(row=1, column=c); cell.font = hf; cell.fill = hfill
        for row in grouped[section]: ws.append(list(row))
        for c in range(1, len(headers) + 1):
            ws.column_dimensions[get_column_letter(c)].width = 25
    buf = io.BytesIO(); wb.save(buf); buf.seek(0); return buf

def export_comparison_to_excel(comparison_df):
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "Сравнение смет"
    headers = list(comparison_df.columns)
    ws.append(headers)
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c); cell.font = hf; cell.fill = hfill
    status_colors = {
        "✅ Совпадает": "C8E6C9",
        "⚠️ Расходится цена": "FFF9C4",
        "⚠️ Расходится объём": "FFE0B2",
        "⚠️ Расходится и цена, и объём": "FFCCBC",
        "❌ Только в смете A": "FFCDD2",
        "❌ Только в смете B": "D1C4E9",
    }
    for _, row in comparison_df.iterrows():
        ws.append(list(row))
        status = row.get("Статус", "")
        color = status_colors.get(status)
        if color:
            row_num = ws.max_row
            fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_num, column=c).fill = fill
    for c in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 25
    buf = io.BytesIO(); wb.save(buf); buf.seek(0); return buf

def export_errors_to_excel(errors_df):
    import io
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook(); ws = wb.active; ws.title = "Проверка сметы"
    headers = list(errors_df.columns)
    ws.append(headers)
    hf = Font(bold=True, color="FFFFFF", size=11)
    hfill = PatternFill(start_color="FF6B35", end_color="FF6B35", fill_type="solid")
    for c, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=c); cell.font = hf; cell.fill = hfill
    color_map = {
        "🔴 Критично": "FFCDD2",
        "🟡 Внимание": "FFF9C4",
        "🟢 ОК": "C8E6C9",
        "🔵 Инфо": "BBDEFB",
    }
    for _, row in errors_df.iterrows():
        ws.append(list(row))
        level = row.get("Уровень", "")
        color = color_map.get(level)
        if color:
            row_num = ws.max_row
            fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            for c in range(1, len(headers) + 1):
                ws.cell(row=row_num, column=c).fill = fill
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

def norm_name_similarity(name1, name2):
    kws1 = set(extract_keywords(name1, max_keywords=10))
    kws2 = set(extract_keywords(name2, max_keywords=10))
    if not kws1 or not kws2: return 0
    return len(kws1 & kws2) / max(len(kws1), len(kws2))

# ===== ПРОВЕРКА СМЕТЫ =====
def check_rate_in_db(code):
    if not code: return None
    conn = get_db_connection()
    if conn is None: return None
    cursor = conn.cursor()
    cursor.execute("SELECT code, name, unit, base_type, source_edition FROM rates WHERE code = ? LIMIT 1", (code,))
    return cursor.fetchone()

def check_estimate(df, code_col, name_col, unit_col, qty_col, price_col, total_col):
    errors = []
    seen_codes = {}

    for idx, row in df.iterrows():
        try: name = clean_html(row.iloc[name_col]) if pd.notna(row.iloc[name_col]) else ""
        except: name = ""

        if not name or len(name) < 5: continue
        if name.lower().startswith(("раздел", "итого", "всего", "№ п/п", "п/п")): continue

        try: code = str(row.iloc[code_col]).strip() if pd.notna(row.iloc[code_col]) else ""
        except: code = ""
        try: unit = str(row.iloc[unit_col]).strip() if pd.notna(row.iloc[unit_col]) else ""
        except: unit = ""
        try: qty = float(row.iloc[qty_col]) if pd.notna(row.iloc[qty_col]) else None
        except: qty = None
        try: price = float(row.iloc[price_col]) if pd.notna(row.iloc[price_col]) else None
        except: price = None
        try: total = float(row.iloc[total_col]) if pd.notna(row.iloc[total_col]) else None
        except: total = None

        row_num = idx + 1

        if not code:
            errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🟡 Внимание",
                "Ошибка": "Отсутствует код нормы", "Описание": "В строке не указан код нормы (обоснование)", "Детали": "—"})
        if qty is None:
            errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🟡 Внимание",
                "Ошибка": "Отсутствует объём", "Описание": "В строке не указан объём работ", "Детали": "—"})
        if price is None:
            errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🟡 Внимание",
                "Ошибка": "Отсутствует цена", "Описание": "В строке не указана цена за единицу", "Детали": "—"})

        if qty is not None and qty < 0:
            errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🔴 Критично",
                "Ошибка": "Отрицательный объём", "Описание": "Объём не может быть отрицательным", "Детали": f"Значение: {qty}"})
        if price is not None and price < 0:
            errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🔴 Критично",
                "Ошибка": "Отрицательная цена", "Описание": "Цена не может быть отрицательной", "Детали": f"Значение: {price}"})

        if code and not code.startswith(("📦", "❌", "—")):
            rate = check_rate_in_db(code)
            if not rate:
                errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🔴 Критично",
                    "Ошибка": "Код не найден в ФСНБ", "Описание": f"Норма {code} отсутствует в базе ФСНБ-2022",
                    "Детали": "Проверьте код или обновите базу"})
            else:
                norm_unit = (rate[2] or "").lower().strip()
                s_est_unit = unit.lower().strip()
                if norm_unit and s_est_unit:
                    norm_u = norm_unit.replace(" ", "").replace("(", "").replace(")", "")
                    est_u = s_est_unit.replace(" ", "").replace("(", "").replace(")", "")
                    if norm_u not in est_u and est_u not in norm_u:
                        errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🟡 Внимание",
                            "Ошибка": "Разные единицы измерения", "Описание": f"В смете: '{unit}', в норме: '{rate[2]}'",
                            "Детали": f"Код: {code}"})

                if rate[3] == "ГЭСНр":
                    errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🔵 Инфо",
                        "Ошибка": "Ремонтная норма", "Описание": f"Используется норма ГЭСНр (капитальный ремонт): {code}",
                        "Детали": "Проверьте, уместна ли эта норма в новой смете"})

        if code:
            if code in seen_codes:
                errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🟡 Внимание",
                    "Ошибка": "Дубликат кода", "Описание": f"Код {code} уже встречался в строке {seen_codes[code]}",
                    "Детали": "Проверьте, не задвоена ли работа"})
            else:
                seen_codes[code] = row_num

        if qty is not None and price is not None and total is not None:
            expected_total = qty * price
            if expected_total > 0:
                diff_pct = abs(total - expected_total) / expected_total * 100
                if diff_pct > 1:
                    errors.append({"Строка": row_num, "Наименование": name[:100], "Уровень": "🔴 Критично",
                        "Ошибка": "Арифметическая ошибка", "Описание": "Сумма ≠ цена × объём",
                        "Детали": f"Объём: {qty}, Цена: {price}, Ожидается: {expected_total:.2f}, В смете: {total:.2f}"})

    return errors

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
    st.caption("Версия 1.8 — проверка сметы")
    st.caption("© СметаАссистент")

# ===== ВКЛАДКИ =====
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Поиск норм", "📊 Анализ ВОР", "⚖️ Сравнение смет", "🔎 Проверка сметы", "💰 Конъюнктурный анализ"
])

# ===== ВКЛАДКА 1: Поиск норм =====
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
            if results is None: st.error("⚠️ База данных не найдена.")
            elif len(results) == 0: st.warning(f"Ничего не найдено.")
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

# ===== ВКЛАДКА 2: Анализ ВОР =====
with tab2:
    st.subheader("Анализ ВОР с распределением по разделам")
    uploaded_file = st.file_uploader("Файл ВОР (.xlsx, .xls):", type=["xlsx", "xls"], key="vor_file")
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
                with colA: hr = st.number_input("Строка с шапкой:", 0, 50, detected["header_row"], 1)
                with colB: nc = st.number_input("Столбец наименования:", 0, 30, detected["name_col"], 1)
                colC, colD = st.columns(2)
                with colC: uc = st.number_input("Столбец ед. изм.:", 0, 30, detected["unit_col"], 1)
                with colD: qc = st.number_input("Столбец объёма:", 0, 30, detected["qty_col"], 1)
                include_sub = st.checkbox("Включать подпункты", value=False)
            uploaded_file.seek(0)
            df = pd.read_excel(uploaded_file, header=hr)
            st.dataframe(df.head(10), use_container_width=True)
            if st.button("🤖 Подобрать нормы", use_container_width=True, key="btn_vor"):
                results_data = []
                counter = 0
                progress = st.progress(0)
                for idx, row in df.iterrows():
                    try: work_name = clean_html(row.iloc[nc]) if pd.notna(row.iloc[nc]) else ""
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
                    res = {"№": counter, "Работа из ВОР": work_name[:200], "Ед. изм. (ВОР)": unit_val,
                           "Объём": qty_val, "Код нормы": "", "Наименование нормы": "",
                           "Тип базы": "", "Раздел": "", "Код вручную": ""}
                    rate_code = None
                    if is_material(work_name, unit_val):
                        res["Код нормы"] = "📦 Материал"; res["Наименование нормы"] = "Норма не требуется"; res["Тип базы"] = "—"
                    else:
                        matches = search_norms_fts(work_name, unit_val=unit_val, limit=3)
                        if matches:
                            m = matches[0]; rate_code = m["code"]
                            res["Код нормы"] = m["code"]; res["Наименование нормы"] = m["name"][:150]; res["Тип базы"] = m["base_type"]
                        else:
                            res["Код нормы"] = "❌ не найдено"; res["Наименование нормы"] = "—"; res["Тип базы"] = "—"
                    res["Раздел"] = define_section(work_name, rate_code)
                    results_data.append(res)
                    if len(df) > 0: progress.progress(min((idx+1)/len(df), 1.0))
                progress.empty()
                if results_data:
                    results_df = pd.DataFrame(results_data)
                    section_order = {s: i for i, s in enumerate(SECTIONS_ORDER)}
                    results_df["_sort"] = results_df["Раздел"].map(section_order).fillna(99)
                    results_df = results_df.sort_values("_sort").drop(columns=["_sort"]).reset_index(drop=True)
                    st.markdown("### 📊 Сводка по разделам")
                    section_counts = results_df.groupby("Раздел").size().to_dict()
                    cols = st.columns(3)
                    col_idx = 0
                    for section in SECTIONS_ORDER:
                        if section in section_counts:
                            with cols[col_idx % 3]: st.metric(section[:30], f"{section_counts[section]} работ")
                            col_idx += 1
                    st.markdown("### 🎯 Результаты")
                    st.dataframe(results_df, use_container_width=True, height=500)
                    st.download_button("📥 Скачать Excel", data=export_vor_to_excel(results_df),
                        file_name="ВОР_с_разделами.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                    total = len(results_data)
                    mats = sum(1 for r in results_data if r["Код нормы"] == "📦 Материал")
                    found = sum(1 for r in results_data if r["Код нормы"] and r["Код нормы"] not in ["📦 Материал", "❌ не найдено"])
                    nf = sum(1 for r in results_data if r["Код нормы"] == "❌ не найдено")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Всего", total); c2.metric("✅ Найдено", found)
                    c3.metric("📦 Материалов", mats); c4.metric("❌ Не найдено", nf)
        except Exception as e:
            st.error(f"Ошибка: {e}")
    else:
        st.info("📁 Загрузите файл ВОР.")

# ===== ВКЛАДКА 3: Сравнение смет =====
with tab3:
    st.subheader("Сравнение двух смет")
    colA, colB = st.columns(2)
    with colA:
        st.markdown("**📄 Смета A**")
        file_a = st.file_uploader("Смета A (.xlsx)", type=["xlsx", "xls"], key="file_a")
    with colB:
        st.markdown("**📄 Смета B**")
        file_b = st.file_uploader("Смета B (.xlsx)", type=["xlsx", "xls"], key="file_b")

    if file_a and file_b:
        import pandas as pd
        try:
            det_a = detect_vor_structure(file_a)
            det_b = detect_vor_structure(file_b)

            with st.expander("📄 Настройки для сметы A", expanded=False):
                a_row = st.number_input("Строка с шапкой A:", 0, 50, det_a["header_row"], 1, key="a_row")
                c1, c2 = st.columns(2)
                with c1: a_name = st.number_input("Столбец наименования A:", 0, 30, det_a["name_col"], 1, key="a_name")
                with c2: a_unit = st.number_input("Столбец ед. изм. A:", 0, 30, det_a["unit_col"], 1, key="a_unit")
                c3, c4 = st.columns(2)
                with c3: a_qty = st.number_input("Столбец объёма A:", 0, 30, det_a["qty_col"], 1, key="a_qty")
                with c4: a_code = st.number_input("Столбец кода нормы A:", 0, 30, det_a["name_col"] + 1, 1, key="a_code")
                c5, c6 = st.columns(2)
                with c5: a_price = st.number_input("Столбец цены A:", 0, 30, det_a["qty_col"] + 1, 1, key="a_price")
                with c6: a_total = st.number_input("Столбец суммы A:", 0, 30, det_a["qty_col"] + 2, 1, key="a_total")

            with st.expander("📄 Настройки для сметы B", expanded=False):
                b_row = st.number_input("Строка с шапкой B:", 0, 50, det_b["header_row"], 1, key="b_row")
                c1, c2 = st.columns(2)
                with c1: b_name = st.number_input("Столбец наименования B:", 0, 30, det_b["name_col"], 1, key="b_name")
                with c2: b_unit = st.number_input("Столбец ед. изм. B:", 0, 30, det_b["unit_col"], 1, key="b_unit")
                c3, c4 = st.columns(2)
                with c3: b_qty = st.number_input("Столбец объёма B:", 0, 30, det_b["qty_col"], 1, key="b_qty")
                with c4: b_code = st.number_input("Столбец кода нормы B:", 0, 30, det_b["name_col"] + 1, 1, key="b_code")
                c5, c6 = st.columns(2)
                with c5: b_price = st.number_input("Столбец цены B:", 0, 30, det_b["qty_col"] + 1, 1, key="b_price")
                with c6: b_total = st.number_input("Столбец суммы B:", 0, 30, det_b["qty_col"] + 2, 1, key="b_total")

            if st.button("⚖️ Сравнить сметы", use_container_width=True, key="btn_compare"):
                file_a.seek(0); file_b.seek(0)
                df_a = pd.read_excel(file_a, header=a_row)
                df_b = pd.read_excel(file_b, header=b_row)
                st.success(f"Загружено: смета A — **{len(df_a)}**, смета B — **{len(df_b)}**")

                rows_a = []
                for idx, row in df_a.iterrows():
                    try: name = clean_html(row.iloc[a_name]) if pd.notna(row.iloc[a_name]) else ""
                    except: continue
                    if not name or len(name) < 5: continue
                    if name.lower().startswith(("раздел", "итого", "всего", "№ п/п", "п/п")): continue
                    try: code = str(row.iloc[a_code]).strip() if pd.notna(row.iloc[a_code]) else ""
                    except: code = ""
                    try: unit = str(row.iloc[a_unit]).strip() if pd.notna(row.iloc[a_unit]) else ""
                    except: unit = ""
                    try: qty = row.iloc[a_qty] if pd.notna(row.iloc[a_qty]) else None
                    except: qty = None
                    try: price = row.iloc[a_price] if pd.notna(row.iloc[a_price]) else None
                    except: price = None
                    try: total = row.iloc[a_total] if pd.notna(row.iloc[a_total]) else None
                    except: total = None
                    rows_a.append({"name": name, "code": code, "unit": unit, "qty": qty, "price": price, "total": total})

                rows_b = []
                for idx, row in df_b.iterrows():
                    try: name = clean_html(row.iloc[b_name]) if pd.notna(row.iloc[b_name]) else ""
                    except: continue
                    if not name or len(name) < 5: continue
                    if name.lower().startswith(("раздел", "итого", "всего", "№ п/п", "п/п")): continue
                    try: code = str(row.iloc[b_code]).strip() if pd.notna(row.iloc[b_code]) else ""
                    except: code = ""
                    try: unit = str(row.iloc[b_unit]).strip() if pd.notna(row.iloc[b_unit]) else ""
                    except: unit = ""
                    try: qty = row.iloc[b_qty] if pd.notna(row.iloc[b_qty]) else None
                    except: qty = None
                    try: price = row.iloc[b_price] if pd.notna(row.iloc[b_price]) else None
                    except: price = None
                    try: total = row.iloc[b_total] if pd.notna(row.iloc[b_total]) else None
                    except: total = None
                    rows_b.append({"name": name, "code": code, "unit": unit, "qty": qty, "price": price, "total": total})

                used_b = set()
                comparison = []
                for ra in rows_a:
                    match_b = None
                    match_type = ""
                    if ra["code"]:
                        for i, rb in enumerate(rows_b):
                            if i in used_b: continue
                            if rb["code"] and rb["code"] == ra["code"]:
                                match_b = rb; used_b.add(i); match_type = "по коду"; break
                    if not match_b:
                        best_score = 0; best_idx = -1
                        for i, rb in enumerate(rows_b):
                            if i in used_b: continue
                            score = norm_name_similarity(ra["name"], rb["name"])
                            if score > best_score: best_score = score; best_idx = i
                        if best_score >= 0.6:
                            match_b = rows_b[best_idx]; used_b.add(best_idx)
                            match_type = f"по названию ({int(best_score*100)}%)"
                    if match_b:
                        diff_price = False; diff_qty = False
                        if ra["price"] is not None and match_b["price"] is not None:
                            try:
                                if abs(float(ra["price"]) - float(match_b["price"])) > 0.01: diff_price = True
                            except: pass
                        if ra["qty"] is not None and match_b["qty"] is not None:
                            try:
                                if abs(float(ra["qty"]) - float(match_b["qty"])) > 0.001: diff_qty = True
                            except: pass
                        if diff_price and diff_qty: status = "⚠️ Расходится и цена, и объём"
                        elif diff_price: status = "⚠️ Расходится цена"
                        elif diff_qty: status = "⚠️ Расходится объём"
                        else: status = "✅ Совпадает"
                        comparison.append({"Статус": status, "Способ сопоставления": match_type,
                            "Код A": ra["code"], "Наименование A": ra["name"][:100],
                            "Ед. A": ra["unit"], "Объём A": ra["qty"], "Цена A": ra["price"], "Сумма A": ra["total"],
                            "Код B": match_b["code"], "Наименование B": match_b["name"][:100],
                            "Ед. B": match_b["unit"], "Объём B": match_b["qty"], "Цена B": match_b["price"], "Сумма B": match_b["total"]})
                    else:
                        comparison.append({"Статус": "❌ Только в смете A", "Способ сопоставления": "—",
                            "Код A": ra["code"], "Наименование A": ra["name"][:100],
                            "Ед. A": ra["unit"], "Объём A": ra["qty"], "Цена A": ra["price"], "Сумма A": ra["total"],
                            "Код B": "—", "Наименование B": "—", "Ед. B": "—", "Объём B": "—", "Цена B": "—", "Сумма B": "—"})

                for i, rb in enumerate(rows_b):
                    if i not in used_b:
                        comparison.append({"Статус": "❌ Только в смете B", "Способ сопоставления": "—",
                            "Код A": "—", "Наименование A": "—", "Ед. A": "—", "Объём A": "—", "Цена A": "—", "Сумма A": "—",
                            "Код B": rb["code"], "Наименование B": rb["name"][:100],
                            "Ед. B": rb["unit"], "Объём B": rb["qty"], "Цена B": rb["price"], "Сумма B": rb["total"]})

                comparison_df = pd.DataFrame(comparison)
                st.markdown("### 📊 Сводка")
                status_counts = comparison_df["Статус"].value_counts().to_dict()
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("✅ Совпадает", status_counts.get("✅ Совпадает", 0))
                c2.metric("⚠️ Расходится", sum(v for k, v in status_counts.items() if k.startswith("⚠️")))
                c3.metric("❌ Только в A", status_counts.get("❌ Только в смете A", 0))
                c4.metric("❌ Только в B", status_counts.get("❌ Только в смете B", 0))
                statuses = ["Все"] + list(status_counts.keys())
                selected_status = st.selectbox("Фильтр:", statuses)
                filtered_df = comparison_df if selected_status == "Все" else comparison_df[comparison_df["Статус"] == selected_status]
                st.dataframe(filtered_df, use_container_width=True, height=500)
                st.download_button("📥 Скачать Excel", data=export_comparison_to_excel(comparison_df),
                    file_name="Сравнение_смет.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
        except Exception as e:
            st.error(f"Ошибка: {e}")
    else:
        st.info("📁 Загрузите обе сметы.")

# ===== ВКЛАДКА 4: ПРОВЕРКА СМЕТЫ =====
with tab4:
    st.subheader("🔎 Проверка сметы на ошибки")
    st.caption("Загрузите смету — ассистент найдёт типичные ошибки: несуществующие коды, несовпадение единиц, дубликаты, арифметические ошибки.")

    check_file = st.file_uploader("Загрузите смету (.xlsx)", type=["xlsx", "xls"], key="check_file")

    if check_file:
        import pandas as pd
        try:
            det = detect_vor_structure(check_file)
            st.markdown(f"""
            <div class="detect-box">
                🤖 Структура: шапка на строке <b>{det["header_row"] + 1}</b>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("🔧 Настройки чтения и столбцов", expanded=False):
                c_row = st.number_input("Строка с шапкой:", 0, 50, det["header_row"], 1, key="c_row")
                c1, c2 = st.columns(2)
                with c1: c_code = st.number_input("Столбец кода нормы:", 0, 30, det["name_col"] - 1 if det["name_col"] > 0 else 0, 1, key="c_code")
                with c2: c_name = st.number_input("Столбец наименования:", 0, 30, det["name_col"], 1, key="c_name")
                c3, c4 = st.columns(2)
                with c3: c_unit = st.number_input("Столбец ед. изм.:", 0, 30, det["unit_col"], 1, key="c_unit")
                with c4: c_qty = st.number_input("Столбец объёма:", 0, 30, det["qty_col"], 1, key="c_qty")
                c5, c6 = st.columns(2)
                with c5: c_price = st.number_input("Столбец цены:", 0, 30, det["qty_col"] + 1, 1, key="c_price")
                with c6: c_total = st.number_input("Столбец суммы:", 0, 30, det["qty_col"] + 2, 1, key="c_total")

            if st.button("🔎 Проверить смету", use_container_width=True, key="btn_check"):
                check_file.seek(0)
                df = pd.read_excel(check_file, header=c_row)
                st.success(f"Загружено: **{len(df)}** строк")

                with st.spinner("Проверяю..."):
                    errors = check_estimate(df, c_code, c_name, c_unit, c_qty, c_price, c_total)

                if not errors:
                    st.success("✅ Ошибок не найдено! Смета выглядит корректно.")
                else:
                    st.markdown("### 📊 Сводка ошибок")
                    level_counts = {}
                    for e in errors:
                        level_counts[e["Уровень"]] = level_counts.get(e["Уровень"], 0) + 1

                    cols = st.columns(4)
                    col_idx = 0
                    for level in ["🔴 Критично", "🟡 Внимание", "🔵 Инфо"]:
                        if level in level_counts:
                            with cols[col_idx]:
                                st.metric(level, level_counts[level])
                            col_idx += 1

                    st.markdown("### 📋 Список ошибок")
                    errors_df = pd.DataFrame(errors)
                    levels = ["Все"] + list(level_counts.keys())
                    selected_level = st.selectbox("Фильтр по уровню:", levels, key="level_filter")
                    filtered = errors_df if selected_level == "Все" else errors_df[errors_df["Уровень"] == selected_level]
                    st.dataframe(filtered, use_container_width=True, height=500)
                    st.download_button("📥 Скачать отчёт об ошибках",
                        data=export_errors_to_excel(errors_df),
                        file_name="Проверка_сметы.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True)
                    st.info(f"📊 Всего найдено замечаний: **{len(errors)}**")

        except Exception as e:
            st.error(f"Ошибка: {e}")
    else:
        st.info("📁 Загрузите смету для проверки.")
        st.markdown("""
        **Что проверяется:**
        - 🔴 **Критично:** код нормы не существует в ФСНБ, отрицательные значения, арифметические ошибки.
        - 🟡 **Внимание:** отсутствуют коды, объёмы, цены; дубликаты кодов; разные единицы измерения.
        - 🔵 **Инфо:** использование ремонтных норм ГЭСНр (проверьте уместность).
        """)

# ===== ВКЛАДКА 5: КОНЪЮНКТУРНЫЙ АНАЛИЗ =====
with tab5:
    st.subheader("💰 Конъюнктурный анализ")
    st.caption("Проверка цен в ФГИС ЦС и анализ коммерческих предложений.")
    rq = st.text_input("Название ресурса:", key="ka_q", placeholder="Арматура А500С 12 мм")
    if st.button("🔍 Проверить", use_container_width=True, key="btn_ka") and rq:
        st.info("🔧 Функция в разработке.")

st.divider()
st.caption("🏗️ СметаАссистент — ИИ-помощник, а не замена специалиста.")
import streamlit as st
from supabase import create_client, Client
from collections import defaultdict
from datetime import datetime

# ============================================================
# СТИЛИ (Sferum-like)
# ============================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.main {
    background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
}

.card {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    margin-bottom: 16px;
    transition: transform 0.15s, box-shadow 0.15s;
}

.card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 24px rgba(0,0,0,0.10);
}

.avatar-circle {
    width: 80px;
    height: 80px;
    border-radius: 50%;
    object-fit: cover;
    border: 3px solid #ffffff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.12);
}

.avatar-large {
    width: 140px;
    height: 140px;
    border-radius: 50%;
    object-fit: cover;
    border: 4px solid #ffffff;
    box-shadow: 0 4px 16px rgba(0,0,0,0.15);
}

.student-name {
    font-size: 15px;
    font-weight: 600;
    color: #1a1a1a;
    margin-top: 8px;
    text-align: center;
}

.student-class {
    font-size: 13px;
    color: #6b7280;
    text-align: center;
}

.btn-back {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 8px 16px;
    color: #374151;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
}

.btn-back:hover {
    background: #f3f4f6;
    border-color: #d1d5db;
}

.profile-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 20px;
    padding: 32px;
    color: white;
    margin-bottom: 24px;
    box-shadow: 0 8px 32px rgba(102, 126, 234, 0.25);
}

.date-block {
    background: #ffffff;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
    border-left: 4px solid #667eea;
}

.date-title {
    font-size: 16px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 12px;
}

.hw-photo {
    border-radius: 12px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    transition: transform 0.2s;
}

.hw-photo:hover {
    transform: scale(1.03);
}

.status-badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

.status-pending { background: #fef3c7; color: #92400e; }
.status-checked { background: #d1fae5; color: #065f46; }
.status-graded { background: #dbeafe; color: #1e40af; }

.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
}

.stTabs [data-baseweb="tab"] {
    background: #ffffff;
    border-radius: 10px 10px 0 0;
    padding: 10px 20px;
    font-weight: 500;
    color: #6b7280;
    border: none;
    box-shadow: 0 -2px 8px rgba(0,0,0,0.03);
}

.stTabs [aria-selected="true"] {
    background: #667eea !important;
    color: #ffffff !important;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================
st.set_page_config(
    page_title="Проверка домашних заданий — Физика",
    page_icon="📚",
    layout="wide"
)

# ============================================================
# SUPABASE
# ============================================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# ДАННЫЕ
# ============================================================
SCHOOLS_CONFIG = {
    "СОШ №1 г. Голицыно": ["10", "11"],
    "Маловяземская СОШ": ["9А", "9Б", "9В", "10", "11"],
}

STATUS_LABELS = {
    "pending": ("⏳ Ожидает", "status-pending"),
    "checked": ("✅ Проверено", "status-checked"),
    "graded": ("📝 Оценено", "status-graded"),
}

# ============================================================
# СОСТОЯНИЕ
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "selected_student" not in st.session_state:
    st.session_state.selected_student = None
if "selected_school" not in st.session_state:
    st.session_state.selected_school = None
if "selected_class" not in st.session_state:
    st.session_state.selected_class = None

# ============================================================
# АВТОРИЗАЦИЯ
# ============================================================
if not st.session_state.authenticated:
    st.markdown("<div style='height: 15vh'></div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("""
        <div style='background: #ffffff; border-radius: 20px; padding: 40px; box-shadow: 0 8px 32px rgba(0,0,0,0.08); text-align: center;'>
            <h1 style='margin-bottom: 8px; color: #1f2937;'>🔐 Вход</h1>
            <p style='color: #6b7280; margin-bottom: 24px;'>Для учителя физики</p>
        </div>
        """, unsafe_allow_html=True)
        
        login = st.text_input("Логин", key="login_input")
        password = st.text_input("Пароль", type="password", key="pass_input")
        
        if st.button("Войти", use_container_width=True, type="primary"):
            if login == "teacher" and password == "physics2026":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
    st.stop()

# ============================================================
# БОКОВОЕ МЕНЮ
# ============================================================
with st.sidebar:
    st.markdown("""
    <div style='text-align: center; margin-bottom: 20px;'>
        <h2 style='color: #667eea; margin: 0;'>📚 Физика</h2>
        <p style='color: #9ca3af; font-size: 13px; margin-top: 4px;'>Проверка домашних заданий</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    if st.button("🏠 Главная", use_container_width=True):
        st.session_state.selected_student = None
        st.session_state.selected_school = None
        st.session_state.selected_class = None
        st.rerun()
    
    st.markdown("---")
    
    if st.button("🚪 Выйти", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.selected_student = None
        st.rerun()

# ============================================================
# ФУНКЦИИ
# ============================================================

def get_students():
    result = supabase.table("students").select("*").order("last_name").execute()
    return result.data or []

def get_student_by_id(student_id):
    result = supabase.table("students").select("*").eq("id", student_id).execute()
    return result.data[0] if result.data else None

def get_submissions_by_student(student_id):
    result = supabase.table("submissions").select("*").eq("student_id", student_id).order("due_date", desc=True).execute()
    return result.data or []

def get_homeworks():
    result = supabase.table("homeworks").select("*").order("due_date", desc=True).execute()
    return result.data or []

def update_submissions_by_date(student_id, due_date, status=None, grade=None):
    """Обновляет ВСЕ работы ученика на указанную дату."""
    data = {}
    if status is not None:
        data["status"] = status
    if grade is not None:
        data["grade"] = grade
    if data:
        if due_date and due_date != "Без даты":
            supabase.table("submissions").update(data).eq("student_id", student_id).eq("due_date", due_date).execute()
        else:
            supabase.table("submissions").update(data).eq("student_id", student_id).is_("due_date", "null").execute()

def add_homework(title, textbook_reference, due_date):
    data = {
        "title": title,
        "textbook_reference": textbook_reference,
        "due_date": due_date.isoformat() if due_date else None
    }
    supabase.table("homeworks").insert(data).execute()

# ============================================================
# СТРАНИЦА УЧЕНИКА
# ============================================================
def show_student_page(student_id):
    student = get_student_by_id(student_id)
    if not student:
        st.error("Ученик не найден")
        return
    
    submissions = get_submissions_by_student(student_id)
    
    # Кнопка назад
    col_back, _ = st.columns([1, 5])
    with col_back:
        if st.button("← Назад к списку", use_container_width=True):
            st.session_state.selected_student = None
            st.rerun()
    
    # Шапка профиля
    st.markdown(f"""
    <div class="profile-header">
        <div style="display: flex; align-items: center; gap: 24px;">
            <img src="{student.get('avatar_url', '')}" class="avatar-large" 
                 onerror="this.style.display='none'; this.parentElement.innerHTML += '<div style=\\'width:140px;height:140px;border-radius:50%;background:#fff3;display:flex;align-items:center;justify-content:center;font-size:48px;\\'>🧑‍🎓</div>'">
            <div>
                <h1 style="margin: 0; font-size: 28px; font-weight: 700;">{student['last_name']} {student['first_name']}</h1>
                <p style="margin: 8px 0 0 0; font-size: 16px; opacity: 0.9;">
                    🏫 {student['school']} &nbsp;|&nbsp; 📚 {student['class_number']}
                </p>
                <p style="margin: 4px 0 0 0; font-size: 14px; opacity: 0.7;">
                    Всего работ: {len(submissions)}
                </p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if not submissions:
        st.info("Ученик пока не отправлял домашние задания.")
        return
    
    # Группировка по датам
    groups = defaultdict(list)
    for sub in submissions:
        key = sub.get("due_date") or "Без даты"
        groups[key].append(sub)
    
    st.subheader("📸 Домашние задания")
    
    for due_date, subs in sorted(groups.items(), key=lambda x: (x[0] == "Без даты", x[0]), reverse=True):
        # Определяем общий статус и оценку для группы
        statuses = [s["status"] for s in subs]
        grades = [s.get("grade") for s in subs if s.get("grade")]
        
        group_status = statuses[0] if len(set(statuses)) == 1 else "pending"
        group_grade = grades[0] if len(set(grades)) == 1 and grades else None
        
        status_label, status_class = STATUS_LABELS.get(group_status, ("❓ Неизвестно", ""))
        
        date_display = due_date
        if due_date != "Без даты":
            try:
                dt = datetime.strptime(due_date, "%Y-%m-%d")
                date_display = dt.strftime("%d.%m.%Y")
            except:
                pass
        
        with st.container():
            st.markdown(f'<div class="date-block">', unsafe_allow_html=True)
            
            # Заголовок даты + статус
            col_title, col_badge = st.columns([3, 1])
            with col_title:
                st.markdown(f'<div class="date-title">📅 {date_display}</div>', unsafe_allow_html=True)
            with col_badge:
                st.markdown(f'<span class="status-badge {status_class}">{status_label}</span>', unsafe_allow_html=True)
            
            # Фотографии
            photo_cols = st.columns(min(len(subs), 4))
            for i, sub in enumerate(subs):
                with photo_cols[i % len(photo_cols)]:
                    st.image(sub["photo_url"], width=180)
            
            # Управление статусом
            st.markdown("<div style='margin-top: 12px;'></div>", unsafe_allow_html=True)
            
            col_chk, col_grade, col_save = st.columns([1, 1, 1])
            
            with col_chk:
                checked = st.checkbox(
                    "Проверено", 
                    value=(group_status in ["checked", "graded"]),
                    key=f"chk_{student_id}_{due_date}"
                )
            
            with col_grade:
                grade_options = [None, 5, 4, 3, 2, 1]
                grade_index = grade_options.index(group_grade) if group_grade in grade_options else 0
                new_grade = st.selectbox(
                    "Оценка",
                    grade_options,
                    index=grade_index,
                    format_func=lambda x: "—" if x is None else str(x),
                    key=f"gr_{student_id}_{due_date}"
                )
            
            with col_save:
                st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True)
                if st.button("💾 Сохранить", key=f"save_{student_id}_{due_date}", use_container_width=True):
                    new_status = "graded" if (checked and new_grade) else ("checked" if checked else "pending")
                    update_submissions_by_date(student_id, due_date, status=new_status, grade=new_grade)
                    st.success("Сохранено!")
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# ГЛАВНАЯ: ШКОЛЫ → КЛАССЫ → УЧЕНИКИ
# ============================================================
def show_schools_page():
    st.title("👨‍🎓 Ученики")
    
    students = get_students()
    if not students:
        st.info("Пока нет зарегистрированных учеников.")
        return
    
    # Вкладки школ
    school_names = list(SCHOOLS_CONFIG.keys())
    school_tabs = st.tabs(school_names)
    
    for i, school in enumerate(school_names):
        with school_tabs[i]:
            classes = SCHOOLS_CONFIG[school]
            class_tabs = st.tabs(classes)
            
            for j, cls in enumerate(classes):
                with class_tabs[j]:
                    # Фильтруем учеников
                    class_students = [
                        s for s in students 
                        if s["school"] == school and s["class_number"] == cls
                    ]
                    
                    if not class_students:
                        st.info(f"В {school}, класс {cls} пока нет учеников.")
                        continue
                    
                    st.markdown(f"<p style='color: #6b7280; font-size: 14px; margin-bottom: 16px;'>👥 Всего: {len(class_students)} учеников</p>", unsafe_allow_html=True)
                    
                    # Сетка учеников: по 4 в ряд
                    cols_per_row = 4
                    for row_idx in range(0, len(class_students), cols_per_row):
                        row = class_students[row_idx:row_idx + cols_per_row]
                        cols = st.columns(len(row))
                        
                        for idx, student in enumerate(row):
                            with cols[idx]:
                                avatar = student.get("avatar_url", "")
                                name = f"{student['last_name']}<br>{student['first_name']}"
                                
                                # Карточка ученика
                                st.markdown(f"""
                                <div class="card" style="text-align: center; cursor: pointer; padding: 16px;">
                                    <img src="{avatar}" class="avatar-circle" 
                                         style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover;"
                                         onerror="this.style.display='none'; this.parentElement.querySelector('.fallback').style.display='flex';">
                                    <div class="fallback" style="width: 80px; height: 80px; border-radius: 50%; background: #e5e7eb; display: none; align-items: center; justify-content: center; margin: 0 auto; font-size: 28px;">🧑‍🎓</div>
                                    <div class="student-name">{name}</div>
                                    <div class="student-class">{student['class_number']}</div>
                                </div>
                                """, unsafe_allow_html=True)
                                
                                # Кнопка под карточкой (невидимая зона клика не работает в Streamlit, поэтому делаем кнопку)
                                if st.button(
                                    "Открыть профиль",
                                    key=f"open_{student['id']}",
                                    use_container_width=True
                                ):
                                    st.session_state.selected_student = student["id"]
                                    st.session_state.selected_school = school
                                    st.session_state.selected_class = cls
                                    st.rerun()

# ============================================================
# ЗАДАНИЯ
# ============================================================
def show_homeworks_page():
    st.title("📋 Домашние задания")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("➕ Добавить задание")
        with st.form("add_hw"):
            title = st.text_input("Название задания")
            textbook_ref = st.text_input("Номера из учебника", placeholder="№ 145-149, стр. 67")
            due_date = st.date_input("Дата сдачи")
            submitted = st.form_submit_button("Добавить", use_container_width=True, type="primary")
            if submitted:
                if title:
                    add_homework(title, textbook_ref, due_date)
                    st.success("Задание добавлено!")
                    st.rerun()
                else:
                    st.error("Введите название")
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col1:
        homeworks = get_homeworks()
        if not homeworks:
            st.info("Пока нет заданий.")
        else:
            for hw in homeworks:
                due = hw.get("due_date", "")
                due_str = ""
                if due:
                    try:
                        due_str = datetime.strptime(due, "%Y-%m-%d").strftime("%d.%m.%Y")
                    except:
                        due_str = due
                
                st.markdown(f"""
                <div class="card" style="border-left: 4px solid #667eea;">
                    <h4 style="margin: 0 0 6px 0; color: #1f2937;">{hw['title']}</h4>
                    <p style="margin: 0; color: #6b7280; font-size: 14px;">📖 {hw.get('textbook_reference', '—')} &nbsp;|&nbsp; 📅 {due_str or 'Без даты'}</p>
                </div>
                """, unsafe_allow_html=True)

# ============================================================
# СТАТИСТИКА
# ============================================================
def show_stats_page():
    st.title("📊 Статистика")
    
    students = get_students()
    submissions = supabase.table("submissions").select("*").execute().data or []
    homeworks = get_homeworks()
    
    # Метрики
    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("👨‍🎓 Учеников", len(students)),
        ("📋 Заданий", len(homeworks)),
        ("📝 Работ", len(submissions)),
        ("✅ Оценено", len([s for s in submissions if s.get("grade")])),
    ]
    for col, (label, value) in zip([col1, col2, col3, col4], metrics):
        with col:
            st.markdown(f"""
            <div class="card" style="text-align: center; padding: 16px;">
                <div style="font-size: 24px; font-weight: 700; color: #667eea;">{value}</div>
                <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">{label}</div>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("По классам")
        if students:
            class_counts = {}
            for s in students:
                key = f"{s['school'][:10]}... — {s['class_number']}" if len(s['school']) > 10 else f"{s['school']} — {s['class_number']}"
                class_counts[key] = class_counts.get(key, 0) + 1
            
            import pandas as pd
            df = pd.DataFrame([{"Класс": k, "Кол-во": v} for k, v in sorted(class_counts.items())])
            st.bar_chart(df.set_index("Класс"), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_b:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("По статусам")
        if submissions:
            status_counts = {}
            for s in submissions:
                st_val = s["status"]
                label = STATUS_LABELS.get(st_val, (st_val, ""))[0]
                status_counts[label] = status_counts.get(label, 0) + 1
            
            import pandas as pd
            df = pd.DataFrame([{"Статус": k, "Кол-во": v} for k, v in status_counts.items()])
            st.bar_chart(df.set_index("Статус"), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# РОУТИНГ
# ============================================================
if st.session_state.selected_student:
    show_student_page(st.session_state.selected_student)
else:
    page = st.sidebar.radio("Раздел:", ["👨‍🎓 Ученики", "📋 Задания", "📊 Статистика"], label_visibility="collapsed")
    
    if page == "👨‍🎓 Ученики":
        show_schools_page()
    elif page == "📋 Задания":
        show_homeworks_page()
    elif page == "📊 Статистика":
        show_stats_page()

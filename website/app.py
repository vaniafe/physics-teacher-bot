import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime

# ============================================================
# НАСТРОЙКА СТРАНИЦЫ
# ============================================================
st.set_page_config(
    page_title="Проверка домашних заданий — Физика",
    page_icon="📚",
    layout="wide"
)

# ============================================================
# ПОДКЛЮЧЕНИЕ К SUPABASE
# ============================================================
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# АВТОРИЗАЦИЯ
# ============================================================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔐 Вход для учителя")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        login = st.text_input("Логин")
        password = st.text_input("Пароль", type="password")
        if st.button("Войти", use_container_width=True):
            if login == "teacher" and password == "physics2026":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Неверный логин или пароль")
    st.stop()

# ============================================================
# БОКОВОЕ МЕНЮ
# ============================================================
st.sidebar.title("📚 Физика")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Раздел:",
    ["👨‍🎓 Ученики", "📋 Задания", "📝 Проверка работ", "📊 Статистика"]
)

st.sidebar.markdown("---")
if st.sidebar.button("🚪 Выйти"):
    st.session_state.authenticated = False
    st.rerun()

# ============================================================
# ФУНКЦИИ
# ============================================================
status_labels = {"pending": "⏳ Ожидает", "checked": "✅ Проверено", "graded": "📝 Оценено"}

def get_students():
    result = supabase.table("students").select("*").order("last_name").execute()
    return result.data

def get_homeworks():
    result = supabase.table("homeworks").select("*").order("due_date", desc=True).execute()
    return result.data

def get_submissions():
    result = supabase.table("submissions").select("*, students(*)").order("submitted_at", desc=True).execute()
    return result.data

def add_homework(title, textbook_reference, due_date):
    data = {
        "title": title,
        "textbook_reference": textbook_reference,
        "due_date": due_date.isoformat() if due_date else None
    }
    supabase.table("homeworks").insert(data).execute()

def update_submission(sid, homework_id=None, grade=None, teacher_comment=None, status=None):
    data = {}
    if homework_id is not None:
        data["homework_id"] = homework_id
    if grade is not None:
        data["grade"] = grade
    if teacher_comment is not None:
        data["teacher_comment"] = teacher_comment
    if status is not None:
        data["status"] = status
    if data:
        supabase.table("submissions").update(data).eq("id", sid).execute()

# ============================================================
# УЧЕНИКИ
# ============================================================
if page == "👨‍🎓 Ученики":
    st.title("👨‍🎓 Список учеников")
    students = get_students()
    if not students:
        st.info("Пока нет зарегистрированных учеников.")
    else:
        classes = sorted(list(set([s["class_number"] for s in students])))
        selected_class = st.selectbox("Фильтр по классу:", ["Все"] + classes)
        if selected_class != "Все":
            students = [s for s in students if s["class_number"] == selected_class]
        st.markdown(f"**Всего учеников: {len(students)}**")
        for student in students:
            with st.container():
                col1, col2, col3 = st.columns([1, 3, 1])
                with col1:
                    if student.get("avatar_url"):
                        st.image(student["avatar_url"], width=80)
                    else:
                        st.markdown("🧑‍🎓")
                with col2:
                    st.markdown(f"**{student['last_name']} {student['first_name']}**")
                    st.markdown(f"🏫 {student['school']} | 📚 {student['class_number']}")
                with col3:
                    st.markdown(f"ID: `{student['id'][:8]}`")
                st.divider()

# ============================================================
# ЗАДАНИЯ
# ============================================================
elif page == "📋 Задания":
    st.title("📋 Домашние задания")
    col1, col2 = st.columns([2, 1])
    with col2:
        st.subheader("➕ Добавить задание")
        with st.form("add_homework"):
            title = st.text_input("Название задания")
            textbook_ref = st.text_input("Номера из учебника", placeholder="№ 145-149, стр. 67")
            due_date = st.date_input("Дата сдачи")
            submitted = st.form_submit_button("Добавить", use_container_width=True)
            if submitted:
                if title:
                    add_homework(title, textbook_ref, due_date)
                    st.success("Задание добавлено!")
                    st.rerun()
                else:
                    st.error("Введите название задания")
    with col1:
        homeworks = get_homeworks()
        if not homeworks:
            st.info("Пока нет заданий. Добавьте первое справа →")
        else:
            df = pd.DataFrame(homeworks)
            df["due_date"] = pd.to_datetime(df["due_date"]).dt.strftime("%d.%m.%Y")
            df = df.rename(columns={
                "title": "Название",
                "textbook_reference": "Номера из учебника",
                "due_date": "Дата сдачи"
            })
            st.dataframe(df[["Название", "Номера из учебника", "Дата сдачи"]], use_container_width=True, hide_index=True)

# ============================================================
# ПРОВЕРКА РАБОТ
# ============================================================
elif page == "📝 Проверка работ":
    st.title("📝 Проверка домашних заданий")
    submissions = get_submissions()
    homeworks = get_homeworks()
    if not submissions:
        st.info("Пока нет отправленных работ.")
    else:
        col1, col2, col3 = st.columns(3)
        with col1:
            statuses = ["Все", "pending", "checked", "graded"]
            selected_status = st.selectbox("Статус:", statuses, format_func=lambda x: status_labels.get(x, x))
        with col2:
            students = get_students()
            student_names = {s["id"]: f"{s['last_name']} {s['first_name']}" for s in students}
            student_options = ["Все"] + list(student_names.values())
            selected_student = st.selectbox("Ученик:", student_options)
        with col3:
            hw_titles = {h["id"]: h["title"] for h in homeworks}
            hw_options = ["Все"] + list(hw_titles.values())
            selected_hw = st.selectbox("Задание:", hw_options)
        
        filtered = submissions
        if selected_status != "Все":
            filtered = [s for s in filtered if s["status"] == selected_status]
        if selected_student != "Все":
            filtered = [s for s in filtered if student_names.get(s["students"]["id"], "") == selected_student]
        if selected_hw != "Все":
            filtered = [s for s in filtered if hw_titles.get(s.get("homework_id"), "") == selected_hw]
        
        st.markdown(f"**Найдено работ: {len(filtered)}**")
        
        for sub in filtered:
            student = sub["students"]
            with st.expander(
                f"{student['last_name']} {student['first_name']} — "
                f"{student['class_number']} | "
                f"{sub['submitted_at'][:10]} | "
                f"Статус: {status_labels.get(sub['status'], sub['status'])}"
            ):
                col1, col2 = st.columns([1, 2])
                with col1:
                    photo_url = sub.get("photo_url")
                    if photo_url and isinstance(photo_url, str):
                        st.image(photo_url, width=300)
                    else:
                        st.warning("📷 Фото не загружено")
                    st.markdown(f"**Отправлено:** {sub['submitted_at'][:16].replace('T', ' ')}")
                with col2:
                    hw_options_list = [(None, "— Не выбрано —")] + [(h["id"], h["title"]) for h in homeworks]
                    current_hw = sub.get("homework_id")
                    hw_index = next((i for i, (hid, _) in enumerate(hw_options_list) if hid == current_hw), 0)
                    new_hw = st.selectbox("Задание:", hw_options_list, index=hw_index, format_func=lambda x: x[1], key=f"hw_{sub['id']}")
                    
                    grade_options = [None, 5, 4, 3, 2, 1]
                    current_grade = sub.get("grade")
                    grade_index = grade_options.index(current_grade) if current_grade in grade_options else 0
                    new_grade = st.selectbox("Оценка:", grade_options, index=grade_index, format_func=lambda x: "—" if x is None else str(x), key=f"grade_{sub['id']}")
                    
                    current_comment = sub.get("teacher_comment") or ""
                    new_comment = st.text_area("Комментарий учителя:", value=current_comment, key=f"comment_{sub['id']}")
                    
                    status_options = ["pending", "checked", "graded"]
                    status_index = status_options.index(sub["status"]) if sub["status"] in status_options else 0
                    new_status = st.selectbox("Статус:", status_options, index=status_index, format_func=lambda x: status_labels.get(x, x), key=f"status_{sub['id']}")
                    
                    if st.button("💾 Сохранить", key=f"save_{sub['id']}", use_container_width=True):
                        update_submission(sub["id"], homework_id=new_hw[0], grade=new_grade, teacher_comment=new_comment if new_comment else None, status=new_status)
                        st.success("Сохранено!")
                        st.rerun()

# ============================================================
# СТАТИСТИКА
# ============================================================
elif page == "📊 Статистика":
    st.title("📊 Статистика")
    students = get_students()
    submissions = get_submissions()
    homeworks = get_homeworks()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Всего учеников", len(students))
    with col2:
        st.metric("Всего заданий", len(homeworks))
    with col3:
        st.metric("Отправлено работ", len(submissions))
    with col4:
        graded = len([s for s in submissions if s.get("grade")])
        st.metric("Оценено работ", graded)
    
    st.markdown("---")
    
    if students:
        st.subheader("Ученики по классам")
        class_counts = {}
        for s in students:
            cn = s["class_number"]
            class_counts[cn] = class_counts.get(cn, 0) + 1
        df_classes = pd.DataFrame([{"Класс": k, "Количество": v} for k, v in sorted(class_counts.items())])
        st.bar_chart(df_classes.set_index("Класс"))
    
    if submissions:
        st.subheader("Статус работ")
        status_counts = {}
        for s in submissions:
            st_val = s["status"]
            status_counts[st_val] = status_counts.get(st_val, 0) + 1
        df_status = pd.DataFrame([{"Статус": status_labels.get(k, k), "Количество": v} for k, v in status_counts.items()])
        st.bar_chart(df_status.set_index("Статус"))

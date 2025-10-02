import streamlit as st
import openai
import os
from dotenv import load_dotenv
from parse_hh import parse_vacancy, parse_resume # Импортируем наши новые функции

# Загружаем переменные окружения (API-ключ)
load_dotenv()
api_key = os.getenv("API_KEY")

# Инициализируем клиент OpenAI с проверкой наличия ключа
if not api_key:
    st.error("API-ключ OpenAI не найден. Пожалуйста, добавьте его в файл .env")
    st.stop()
client = openai.OpenAI(api_key=api_key)

# Системный промпт для модели
SYSTEM_PROMPT = '''
Проскорь кандидата, насколько он подходит для данной вакансии.
Сначала напиши короткий анализ, который будет пояснять оценку.
Отдельно оцени качество заполнения резюме (понятно ли, с какими задачами сталкивался кандидат и каким образом их решал?). Эта оценка должна учитываться при выставлении финальной оценки - нам важно нанимать таких кандидатов, которые могут рассказать про свою работу.
Потом представь результат в виде оценки от 1 до 10.
'''.strip()

def request_gpt(system_prompt, user_prompt):
    """Отправляет запрос к API OpenAI и возвращает ответ."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"Произошла ошибка при обращении к API OpenAI: {e}")
        return None

# --- ИЗМЕНЕНИЯ В ИНТЕРФЕЙСЕ ---

st.title("CV Scoring App")
st.write("Приложение для автоматической оценки кандидатов с hh.ru.")

# Поля для ввода URL вместо больших текстовых областей
job_url = st.text_input("Вставьте ссылку на вакансию (hh.ru/vacancy/...)")
cv_url = st.text_input("Вставьте ссылку на резюме (hh.ru/resume/...)")

if st.button("Оценить кандидата"):
    # Проверяем, что оба URL введены
    if not job_url or not cv_url:
        st.warning("Пожалуйста, вставьте ссылки на вакансию и на резюме.")
    else:
        # Блок с индикатором загрузки и парсинга
        with st.spinner("Загружаем и анализируем данные..."):
            # Шаг 1: Парсим вакансию и резюме
            job_description = parse_vacancy(job_url)
            cv_text = parse_resume(cv_url)

            # Проверяем, не вернули ли функции парсинга ошибки
            error_found = False
            if job_description.startswith("Ошибка:"):
                st.error(f"Не удалось получить описание вакансии: {job_description}")
                error_found = True
            
            if cv_text.startswith("Ошибка:"):
                st.error(f"Не удалось получить резюме: {cv_text}")
                error_found = True

            # Если ошибок нет, продолжаем работу
            if not error_found:
                st.info("Данные с hh.ru успешно загружены. Отправляем запрос к AI...")
                
                # Шаг 2: Формируем промпт и отправляем в GPT
                user_prompt = f"# ВАКАНСИЯ\n{job_description}\n\n# РЕЗЮМЕ\n{cv_text}"
                response_text = request_gpt(SYSTEM_PROMPT, user_prompt)
                
                if response_text:
                    st.success("Оценка готова!")
                    st.write("### Результат оценки:")
                    st.write(response_text)
                    
                    # Показываем спарсенные тексты для удобства
                    with st.expander("Показать загруженное описание вакансии"):
                        st.markdown(job_description)
                    with st.expander("Показать загруженное резюме"):
                        st.markdown(cv_text)

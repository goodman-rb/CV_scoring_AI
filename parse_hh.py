import re
import sys
import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time

def _fetch_html_selenium(url: str, debug_filename: str | None = None) -> str | None:
    """
    Загружает HTML с помощью Selenium для динамических страниц.
    """
    options = Options()
    options.add_argument('--headless')  # Без открытия окна браузера
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        
        # Ждем загрузки контента (до 10 секунд)
        time.sleep(3)  # Даем время на загрузку JavaScript
        
        html_content = driver.page_source
        driver.quit()
        
        if debug_filename:
            try:
                with open(debug_filename, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"INFO: HTML сохранен в '{debug_filename}'", file=sys.stderr)
            except Exception as e:
                print(f"WARNING: Не удалось сохранить файл: {e}", file=sys.stderr)
        
        return html_content
    except Exception as e:
        print(f"Ошибка Selenium: {e}", file=sys.stderr)
        return None

def _fetch_html(url: str, debug_filename: str | None = None) -> str | None:
    """
    Универсальная функция для загрузки HTML-контента по URL.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://hh.ru/',
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        html_text = response.text

        if debug_filename:
            try:
                with open(debug_filename, 'w', encoding='utf-8') as f:
                    f.write(html_text)
                print(f"INFO: HTML сохранен в '{debug_filename}'", file=sys.stderr)
            except Exception as e:
                print(f"WARNING: Не удалось сохранить файл: {e}", file=sys.stderr)

        return html_text
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при загрузке URL {url}: {e}", file=sys.stderr)
        return None

def _postprocess_resume_markdown(markdown_text: str) -> str:
    """
    Улучшает читаемость Markdown-текста резюме.
    """
    markdown_text = re.sub(
        r'##\s*Опыт работы\s*(\d+.*месяц.*)',
        r'## Опыт работы\n\n**Общий стаж:** \1',
        markdown_text
    )

    def fix_experience_line(match):
        date_part = match.group(1).strip()
        duration_part = match.group(2).strip()
        return f"**{date_part}** — {duration_part}"

    markdown_text = re.sub(
        r'([А-Яа-я]+\s*\d{4}\s*—\s*[А-Яа-я\s]+)(\d+\s+лет?\s+\d+\s+месяц.*)',
        fix_experience_line,
        markdown_text
    )
    markdown_text = re.sub(r'\*\s*\n', '\n', markdown_text)
    return markdown_text

def parse_vacancy(url: str, debug: bool = False) -> str:
    """
    Парсит описание вакансии с hh.ru по URL.
    """
    if not url or not url.startswith("https://hh.ru/vacancy/"):
        return "Ошибка: Некорректный URL вакансии."

    debug_file = "debug_vacancy_page.html" if debug else None
    html_content = _fetch_html(url, debug_filename=debug_file)
    if not html_content:
        return "Ошибка: Не удалось загрузить страницу вакансии."

    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        desc_div = soup.find('div', {'data-qa': 'vacancy-description'})
        if desc_div:
            return md(str(desc_div), strip=['div', 'span']).strip()
        else:
            return "Ошибка: Блок с описанием вакансии не найден на странице."
    except Exception as e:
        return f"Ошибка при парсинге вакансии: {e}"


def parse_resume(url: str, debug: bool = False) -> str:
    """
    Парсит резюме с hh.ru по URL используя Selenium.
    """
    if not url or not url.startswith("https://hh.ru/resume/"):
        return "Ошибка: Некорректный URL резюме."

    debug_file = "debug_resume_page.html" if debug else None
    # Используем Selenium для резюме
    html_content = _fetch_html_selenium(url, debug_filename=debug_file)
    if not html_content:
        return "Ошибка: Не удалось загрузить страницу резюме."

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        if soup.find(string=lambda t: t and 'доступ к резюме закрыт' in t.lower()):
            return "Ошибка: Доступ к резюме закрыт. Требуется авторизация как работодатель."

        # Ищем блок с резюме - новая структура hh.ru
        resume_block = (
            soup.find('div', class_='resume-wrapper') or
            soup.find('div', class_='resume-applicant') or
            soup.find('main', class_='main-content') or
            soup.find('div', {'id': 'HH-React-Root'})
        )
        
        if not resume_block:
            return "Ошибка: Не удалось найти основной блок с данными резюме."

        for elem in resume_block.select('[data-qa*="button"], .bloko-icon, script, style'):
            elem.decompose()

        markdown = md(str(resume_block), heading_style="ATX", strip=['div', 'span', 'section', 'article']).strip()
        if not markdown:
            return "Ошибка: Резюме оказалось пустым после обработки."
        
        return _postprocess_resume_markdown(markdown)

    except Exception as e:
        return f"Ошибка при парсинге резюме: {e}"

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Использование для теста:", file=sys.stderr)
        print("  python parse_hh.py <URL вакансии или резюме>", file=sys.stderr)
        sys.exit(1)
        
    test_url = sys.argv[1]
    print(f"--- Запуск теста для URL: {test_url} ---", file=sys.stderr)

    if "/resume/" in test_url:
        print("\n--- Тестирование парсинга РЕЗЮМЕ ---", file=sys.stderr)
        result = parse_resume(test_url, debug=True)
    elif "/vacancy/" in test_url:
        print("\n--- Тестирование парсинга ВАКАНСИИ ---", file=sys.stderr)
        result = parse_vacancy(test_url, debug=True)
    else:
        result = "Ошибка: URL не похож на ссылку на вакансию или резюме hh.ru"

    print("\n--- РЕЗУЛЬТАТ ПАРСИНГА ---")
    print(result)
"""
Генерирует под конкретную вакансию:
  1) HTML-лендинг на основе ТВОЕГО базового резюме (artemiy-spasenov-pm.html)
  2) сопроводительное письмо в деловом регистре

Базовый файл тянется из репозитория при каждой генерации — правишь дизайн
у себя, генератор автоматически подхватывает новый.

Принцип зашит в промпт жёстко: стратегический перевод реального опыта — да,
выдуманные факты, цифры, компании и компетенции — нет.
"""
import datetime as dt
import html
import json
import logging
import re

import requests

from config import (BASE_RESUME_FILE, GITHUB_BRANCH, GITHUB_OWNER, GITHUB_REPO,
                    GITHUB_TOKEN, MODEL, OPENROUTER_KEY, OPENROUTER_URL, PROFILE)

log = logging.getLogger("generator")

SYSTEM = """Ты помогаешь кандидату готовить резюме под конкретную вакансию.

ЖЕЛЕЗНОЕ ПРАВИЛО: можно переставлять акценты и переводить реальный опыт на язык
вакансии. НЕЛЬЗЯ выдумывать факты. Запрещено изобретать цифры, метрики,
проценты, названия компаний, продуктов, технологий, должностей, сертификатов и
достижений, которых нет в профиле кандидата. Если в профиле нет цифры — не пиши
цифру. Каждое утверждение должно быть защитимо на собеседовании.

Если опыт не покрывает требование вакансии — не изображай, что покрывает.
Опирайся на смежный реальный опыт честно.

Пиши по-русски, деловым тоном, без канцелярита и пафоса. Не используй слова
«динамичный», «проактивный», «стрессоустойчивый», «амбициозный».

Верни СТРОГО валидный JSON без markdown-обёрток:
{
  "tagline": "1-2 предложения в шапку резюме под эту роль, от первого лица, живо и по делу",
  "fit": [
    {"label": "короткий ярлык, 1-3 слова", "title": "заголовок 3-6 слов", "text": "2-3 предложения: почему подхожу, с опорой на реальный опыт"}
  ],
  "cover_letter": "сопроводительное письмо, 3-5 предложений"
}
В "fit" ровно три объекта.

ТРЕБОВАНИЯ К СОПРОВОДИТЕЛЬНОМУ — это самая важная часть, рекрутёр читает
первые две строки и решает, открывать ли резюме:
- Первое предложение — сразу самое сильное совпадение с вакансией, конкретикой.
  НЕ начинай с «Меня заинтересовала вакансия», «Здравствуйте», «Пишу вам».
- Дальше 2-3 предложения: чем именно закрою задачи роли. Конкретика вместо общих слов.
- Последняя строка — одна короткая фраза о готовности обсудить. РОВНО ОДНА.
- Никакой воды и повторов. Запрещены фразы: «может быть полезен вашей компании»,
  «открыт к диалогу», «подробное обсуждение возможностей сотрудничества»,
  «имею значительный опыт», «позволяет эффективно решать задачи».
- Не пересказывай резюме целиком — дай зацепку, ради которой откроют ссылку.
- Тон деловой и уверенный, но живой. Без канцелярита."""


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    a, b = text.find("{"), text.rfind("}")
    if a == -1 or b == -1:
        raise ValueError(f"нет JSON: {text[:200]}")
    return json.loads(text[a:b + 1])


def fetch_base_resume() -> str:
    """Тянет базовый лендинг из репозитория."""
    url = (f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
           f"/contents/{BASE_RESUME_FILE}")
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {GITHUB_TOKEN}",
                 "Accept": "application/vnd.github.raw",
                 "X-GitHub-Api-Version": "2022-11-28"},
        params={"ref": GITHUB_BRANCH},
        timeout=60,
    )
    r.raise_for_status()
    r.encoding = "utf-8"
    log.info("базовое резюме получено: %d символов", len(r.text))
    return r.text


def generate_content(title: str, company: str, salary: str, jd: str) -> dict:
    jd_block = (f"ТЕКСТ ВАКАНСИИ:\n{jd[:5000]}" if jd else
                "ТЕКСТ ВАКАНСИИ: не загрузился. Опирайся на название и компанию.")
    user = (f"ПРОФИЛЬ КАНДИДАТА:\n{PROFILE}\n\n"
            f"ВАКАНСИЯ: {title}\n"
            f"КОМПАНИЯ: {company or 'не указана'}\n"
            f"ЗАРПЛАТА В ОБЪЯВЛЕНИИ: {salary or 'не указана'}\n\n{jd_block}")

    r = requests.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {OPENROUTER_KEY}",
                 "Content-Type": "application/json"},
        json={"model": MODEL,
              "messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": user}],
              "temperature": 0.4, "max_tokens": 1800},
        timeout=120,
    )
    r.raise_for_status()
    data = _extract_json(r.json()["choices"][0]["message"]["content"])
    if not data.get("tagline") or not data.get("fit"):
        raise ValueError("модель вернула неполный ответ")
    return data


def _fit_section(role: str, company: str, fit: list) -> str:
    """Блок «почему подхожу» в родных классах базового резюме."""
    cards = []
    for i, item in enumerate(fit[:3], 1):
        label = html.escape(str(item.get("label", "")))[:40]
        head = html.escape(str(item.get("title", "")))[:80]
        text = html.escape(str(item.get("text", "")))
        cards.append(
            f'      <div class="approach-card reveal">\n'
            f'        <div class="num">{i:02d} / {label}</div>\n'
            f'        <h3>{head}</h3>\n'
            f'        <p>{text}</p>\n'
            f'      </div>'
        )
    where = f" в {html.escape(company)}" if company else ""
    return (
        '\n<!-- TARGETED -->\n'
        '<section id="fit">\n'
        '  <div class="container">\n'
        '    <div class="section-head reveal">\n'
        f'      <div class="section-label rust">Под вакансию{where}</div>\n'
        f'      <h2 class="section-title">Почему подхожу на <span class="italic rust">'
        f'{html.escape(role)}</span></h2>\n'
        '    </div>\n'
        '    <div class="approach-grid">\n' + "\n".join(cards) + '\n'
        '    </div>\n'
        '  </div>\n'
        '</section>\n'
    )


def build_html(base: str, role: str, company: str, content: dict) -> str:
    """Правит базовый лендинг под вакансию. Дизайн не трогаем."""
    out = base
    role_esc = html.escape(role)
    co_esc = html.escape(company) if company else ""

    # 1. title
    out = re.sub(r"<title>.*?</title>",
                 f"<title>Артемий Спасенов — {role_esc}</title>", out, count=1, flags=re.S)

    # 2. meta description
    desc = f"Резюме под вакансию «{role_esc}»" + (f", {co_esc}." if co_esc else ".")
    desc += " Project Manager, 7+ лет в B2B-проектах."
    out = re.sub(r'(<meta name="description" content=")[^"]*(")',
                 lambda m: m.group(1) + desc + m.group(2), out, count=1)

    # 3. плашка в шапке
    badge = f"Резюме под вакансию{' · ' + co_esc if co_esc else ''}"
    out = re.sub(r'(<div class="hero-meta[^"]*">\s*<span class="pulse"></span>\s*<span>)[^<]*(</span>)',
                 lambda m: m.group(1) + badge + m.group(2), out, count=1, flags=re.S)

    # 4. таглайн
    tagline = html.escape(str(content["tagline"]))
    out = re.sub(r'(<p class="hero-tagline[^"]*">).*?(</p>)',
                 lambda m: m.group(1) + tagline + m.group(2), out, count=1, flags=re.S)

    # 5. секция «почему подхожу» — сразу после hero
    block = _fit_section(role, company, content["fit"])
    marker = '<section id="about">'
    if marker in out:
        out = out.replace(marker, block + marker, 1)
    else:
        log.warning("не нашёл якорь для fit-блока — вставляю перед </body>")
        out = out.replace("</body>", block + "</body>", 1)

    return out


def slugify(text: str, maxlen: int = 48) -> str:
    table = {"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
             "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
             "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
             "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
             "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"}
    out = []
    for ch in text.lower():
        if ch in table:
            out.append(table[ch])
        elif ch.isalnum() and ch.isascii():
            out.append(ch)
        else:
            out.append("-")
    s = re.sub(r"-{2,}", "-", "".join(out)).strip("-")
    return s[:maxlen].strip("-") or "vacancy"


def generate(vacancy_row, jd: str) -> tuple:
    """Возвращает (filename, html, cover_letter)."""
    title = vacancy_row["title"]
    company = vacancy_row["company"] or ""
    salary = vacancy_row["salary_raw"] or ""

    base = fetch_base_resume()
    content = generate_content(title, company, salary, jd)
    page = build_html(base, title, company, content)

    filename = slugify(f"{title}-{company}" if company else title) + ".html"
    return filename, page, str(content.get("cover_letter", "")).strip()

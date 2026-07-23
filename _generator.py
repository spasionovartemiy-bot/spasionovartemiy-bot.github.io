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

ТАРГЕТИРОВАНИЕ. Резюме должно читаться так, будто написано только под эту
вакансию. Всё нерелевантное надо УБРАТЬ — не потому что это неправда, а потому
что отвлекает и отпугивает: опыт в металлургии в резюме для кофейни только
мешает. Что оставить — выбираешь из готовых списков ниже.

Верни СТРОГО валидный JSON без markdown-обёрток:
{
  "hero_role": "строка роли в шапке, 2-4 слова, максимально близко к названию вакансии",
  "tagline": "1-2 предложения в шапку резюме под эту роль, от первого лица, живо и по делу. Упоминай только релевантные вакансии индустрии",
  "industries": ["из списка ИНДУСТРИИ оставь только релевантные, 3-5 штук, самая близкая первой"],
  "clients": ["из списка КЛИЕНТЫ оставь только уместные, 2-4 штуки"],
  "exp_tags": ["из списка ТЕГИ ОПЫТА оставь релевантные, 3-6 штук"],
  "fit": [
    {"label": "короткий ярлык, 1-3 слова", "title": "заголовок 3-6 слов", "text": "2-3 предложения: почему подхожу, с опорой на реальный опыт"}
  ],
  "cover_letter": "живое сообщение рекрутёру, 4-6 коротких предложений, по структуре ниже"
}
В "fit" ровно три объекта.

ТРЕБОВАНИЯ К СОПРОВОДИТЕЛЬНОМУ — это главное, рекрутёр читает первые две
строки и решает, открывать ли резюме. Нужно живое современное сообщение, а не
деловое письмо. Структура ровно такая:

1. Приветствие одним словом. «Привет» — если компания из IT, продукта, digital,
   стартап. «Добрый день» — если корпорация, банк, промышленность, консалтинг.
2. Кто я — одним предложением, с конкретными навыками ПОД ЭТУ вакансию.
3. Что делал и чего добился — конкретика из профиля. Только реальные факты.
4. Фраза про совпадение с вакансией — своими словами, не шаблоном.
5. Короткий финал: буду рад обсудить / готов созвониться. ОДНА строка.

Итого 4-6 коротких предложений. Пиши как человек, а не как отдел кадров.

Пример нужного тона (структура, не текст для копирования):
«Привет! Я проджект с 7+ годами в B2B — веду проекты end-to-end, от KPI и
бюджета до сдачи. Руководил командами до 15 человек, вёл проекты на 5-20 млн,
привлёк 30+ корпоративных клиентов. Плюс сам пишу автоматизации и держу свои
продукты на проде, так что с разработкой говорю на одном языке. Судя по
описанию, у нас хороший мэтч. Буду рад обсудить детали.»

ЗАПРЕЩЕНО: «меня заинтересовала вакансия», «имею значительный опыт», «может
быть полезен вашей компании», «открыт к диалогу», «подробное обсуждение
возможностей сотрудничества», «позволяет эффективно решать задачи»,
«рассмотрите мою кандидатуру», канцелярит, повторы, вода.
Не пересказывай резюме целиком — дай зацепку, ради которой откроют ссылку.
"""


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
            f"ЗАРПЛАТА В ОБЪЯВЛЕНИИ: {salary or 'не указана'}\n\n"
            f"ИНДУСТРИИ (выбери релевантные): {', '.join(ALL_INDUSTRIES)}\n"
            f"КЛИЕНТЫ (выбери уместные): {', '.join(ALL_CLIENTS)}\n"
            f"ТЕГИ ОПЫТА (выбери релевантные): {', '.join(ALL_EXP_TAGS)}\n\n"
            f"{jd_block}")

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


ALL_INDUSTRIES = ["Нефть и газ", "Металлургия", "Добывающая отрасль", "Банкинг",
                  "Ритейл", "Химия", "ESG & устойчивое развитие", "B2B-консалтинг"]
ALL_CLIENTS = ["ПАО Сбербанк", "ПАО Промсвязьбанк", "Inditex (Новая мода)",
               "АО Тольяттиазот"]
ALL_EXP_TAGS = ["Нефтегаз", "Металлургия", "Добывающая отрасль", "B2B-консалтинг",
                "ESG-консалтинг", "Экологический комплаенс", "Энергоэффективность"]


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip().lower()


def _filter_items(inner, item_pattern, keep, minimum):
    """Оставляет только элементы, чей текст попал в keep. Порядок — как в keep."""
    items = re.findall(item_pattern, inner, re.S)
    if not items:
        return None
    keep_norm = [_norm(k) for k in keep]

    chosen = []
    for kn in keep_norm:                      # порядок по релевантности
        for it in items:
            if _norm(it) == kn and it not in chosen:
                chosen.append(it)
    for it in items:                          # добить до минимума
        if len(chosen) >= minimum:
            break
        if it not in chosen:
            chosen.append(it)
    return chosen or items


def _apply_selection(out, content):
    """Убирает из базового резюме всё, что не относится к вакансии."""
    ind = content.get("industries") or []
    m = re.search(r'(<div class="industries-row">)(.*?)(</div>)', out, re.S)
    if m and ind:
        chosen = _filter_items(m.group(2),
                               r'<span class="industry-chip[^"]*">.*?</span>', ind, 3)
        if chosen:
            chosen = [re.sub(r'class="industry-chip[^"]*"',
                             'class="industry-chip"', c) for c in chosen]
            chosen[0] = chosen[0].replace('class="industry-chip"',
                                          'class="industry-chip accent"')
            inner = "\n      " + "\n      ".join(chosen) + "\n    "
            out = out[:m.start(2)] + inner + out[m.end(2):]

    cl = content.get("clients") or []
    if cl:
        pat = (r'\s*<div class="client">\s*<div class="client-name">(.*?)</div>\s*'
               r'<div class="client-meta">.*?</div>\s*</div>')
        blocks = [(mm.group(0), _norm(mm.group(1)))
                  for mm in re.finditer(pat, out, re.S)]
        keep_norm = [_norm(c) for c in cl]
        keep_blocks = [b for b, n in blocks if n in keep_norm]
        if len(keep_blocks) < 2:                       # не оставляем пусто
            keep_blocks = [b for b, _ in blocks[:2]]
        for b, _ in blocks:
            if b not in keep_blocks:
                out = out.replace(b, "", 1)

    tags = content.get("exp_tags") or []
    if tags:
        def repl(mm):
            chosen = _filter_items(mm.group(2), r'<span class="exp-tag">.*?</span>',
                                   tags, 1)
            if not chosen:
                return mm.group(0)
            return (mm.group(1) + "\n          "
                    + "\n          ".join(chosen) + "\n        " + mm.group(3))
        out = re.sub(r'(<div class="exp-tags">)(.*?)(</div>)', repl, out, flags=re.S)

    return out


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
    hero_role = content.get("hero_role")
    if hero_role:
        out = re.sub(r'(<div class="hero-role[^"]*">).*?(</div>)',
                     lambda m: m.group(1) + html.escape(str(hero_role)) + m.group(2),
                     out, count=1, flags=re.S)

    out = _apply_selection(out, content)

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

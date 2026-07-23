"""
Собирает компактное PDF-резюме на 1-2 страницы из того же контента,
что и веб-версия. Дополнительных запросов к модели не делает.

Веб-лендинг и PDF решают разные задачи: лендинг — произвести впечатление,
PDF — пройти через рекрутёра и ATS. Поэтому тут строгая типографика,
без портрета, анимаций и тёмных заливок.
"""
import datetime as dt
import html
import logging
import re

from weasyprint import CSS, HTML

log = logging.getLogger("pdf")

CSS_TEXT = """
@page {
  size: A4;
  margin: 14mm 15mm 12mm 15mm;
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-family: "DejaVu Sans", sans-serif;
    font-size: 7.5pt;
    color: #9a9a9a;
  }
}
* { box-sizing: border-box; }
body {
  font-family: "DejaVu Sans", sans-serif;
  font-size: 9pt;
  line-height: 1.42;
  color: #1a1a1a;
  margin: 0;
}
a { color: #c2410c; text-decoration: none; }

.name {
  font-size: 20pt;
  font-weight: bold;
  letter-spacing: -0.4pt;
  margin: 0;
}
.role {
  font-size: 10.5pt;
  color: #c2410c;
  font-weight: bold;
  margin: 2pt 0 0 0;
}
.contacts {
  margin-top: 5pt;
  font-size: 8.5pt;
  color: #4a4a4a;
}
.rule { border-bottom: 1.6pt solid #1a1a1a; margin: 7pt 0 9pt 0; }

h2 {
  font-size: 8pt;
  text-transform: uppercase;
  letter-spacing: 1.1pt;
  color: #8a8a8a;
  margin: 0 0 5pt 0;
  padding-bottom: 2.5pt;
  border-bottom: 0.5pt solid #d8d8d8;
  font-weight: bold;
}
section { margin-bottom: 10pt; }

.lede { margin: 0; font-size: 9.5pt; }

ul { margin: 0; padding-left: 11pt; }
li { margin-bottom: 2.2pt; }

.fit li { margin-bottom: 4pt; }
.fit b { color: #1a1a1a; }

.job { margin-bottom: 9pt; }
.job-head { margin-bottom: 1.5pt; }
.job-title { font-weight: bold; font-size: 10pt; }
.job-co { color: #c2410c; font-weight: bold; }
.job-dates { float: right; font-size: 8pt; color: #7a7a7a; padding-top: 2pt; }
.job-note { color: #6a6a6a; font-size: 8pt; margin: 0 0 3pt 0; }

.chips { margin: 0; padding: 0; }
.chip {
  display: inline-block;
  border: 0.5pt solid #d0d0d0;
  border-radius: 7pt;
  padding: 1pt 6pt;
  margin: 0 3pt 3pt 0;
  font-size: 7.5pt;
  color: #4a4a4a;
}
.chip-accent { border-color: #c2410c; color: #c2410c; }

.two { width: 100%; }
.two td { vertical-align: top; width: 50%; padding: 0 8pt 0 0; }

.clients { font-size: 8.5pt; }
.clients b { color: #1a1a1a; }

.edu-item { margin-bottom: 3.5pt; }
.edu-item b { font-size: 9pt; }
.edu-item span { color: #6a6a6a; font-size: 8pt; }

.foot {
  margin-top: 8pt;
  padding-top: 5pt;
  border-top: 0.5pt solid #d8d8d8;
  font-size: 7.5pt;
  color: #8a8a8a;
}
"""

# Реальный опыт — статичен, меняются только теги индустрий под вакансию
JOBS = [
    {
        "title": "Руководитель проектов",
        "company": "Tactise Group",
        "dates": "03.2024 — н. в.",
        "note": "Международная группа: HSE-консалтинг и трансформация культуры "
                "производственной безопасности. Москва, Мумбаи, Дубай. Резидент «Сколково».",
        "bullets": [
            "Планирование: KPI, roadmap, WBS, диаграммы Ганта, оценка сроков и этапов",
            "Бюджет: оценка затрат, контроль расходов, расчёт ROI ключевых инициатив",
            "Управление ожиданиями стейкхолдеров: сроки, риски, эскалации, Change Request",
            "Программа подготовки внутренних тренеров: обучение, супервизия, оценочные листы",
            "Закрытие проектов: Post-Mortem analysis, архивация документации",
        ],
    },
    {
        "title": "Руководитель группы",
        "company": "Экостандарт",
        "dates": "10.2018 — 03.2024",
        "note": "Путь от специалиста 2-й категории до руководителя группы — "
                "четыре ступени за 5,5 лет.",
        "bullets": [
            "Управление командой до 15 человек: обучение, мотивация, оценка",
            "Привлечено 30+ корпоративных клиентов с заключением договоров",
            "Бюджеты проектов 5–20 млн ₽, планирование ресурсов, дорожные карты",
            "20+ внутренних обучений и 5+ курсов для партнёров и заказчиков",
            "Переговоры с ЛПР, pipeline-менеджмент, долгосрочные отношения с клиентами",
        ],
    },
]

CLIENT_META = {
    "ПАО Сбербанк": "банк",
    "ПАО Промсвязьбанк": "банк",
    "Inditex (Новая мода)": "ритейл · мода",
    "АО Тольяттиазот": "химия",
}

SKILLS = [
    ("Управление проектами",
     "Agile · Scrum · Jira · MS Project · roadmap · WBS · Gantt · "
     "risk management · Change Request · Post-Mortem"),
    ("Бизнес и финансы",
     "Бюджеты 5–20 млн ₽ · расчёт ROI · переговоры с ЛПР · "
     "pipeline-менеджмент · B2B-продажи · работа с C-level"),
    ("Технологии",
     "Python и SQL через AI-инструменты · n8n · Docker · собственный сервер · "
     "Cursor · Claude Code · промпт-инжиниринг"),
]

EDU = [
    ("УМЦ им. В.В. Жириновского", "аспирантура — региональная и отраслевая экономика"),
    ("Catholic University in Ružomberok", "магистратура на английском языке, Словакия"),
    ("РУДН им. П. Лумумбы", "магистр — рециклинг отходов производства и потребления"),
    ("РУДН им. П. Лумумбы", "бакалавр — экология и природопользование"),
]


def _esc(s):
    return html.escape(str(s))


def _chips(items, accent_first=True):
    out = []
    for i, it in enumerate(items):
        cls = "chip chip-accent" if (accent_first and i == 0) else "chip"
        out.append(f'<span class="{cls}">{_esc(it)}</span>')
    return "".join(out)


def build_pdf(path, role, company, content, web_url=""):
    """Рендерит PDF. content — то же, что ушло в веб-версию."""
    fit_items = []
    for item in content.get("fit", [])[:3]:
        title = _esc(item.get("title", ""))
        text = _esc(item.get("text", ""))
        fit_items.append(f"<li><b>{title}.</b> {text}</li>")

    exp_tags = content.get("exp_tags") or []
    industries = content.get("industries") or []
    clients = content.get("clients") or []

    jobs_html = []
    for i, j in enumerate(JOBS):
        # теги индустрий показываем только у первой позиции, чтобы не дублировать
        tags = _chips(exp_tags[:4], accent_first=False) if i == 0 and exp_tags else ""
        bullets = "".join(f"<li>{_esc(b)}</li>" for b in j["bullets"])
        jobs_html.append(f"""
        <div class="job">
          <div class="job-head">
            <span class="job-dates">{_esc(j['dates'])}</span>
            <span class="job-title">{_esc(j['title'])}</span> ·
            <span class="job-co">{_esc(j['company'])}</span>
          </div>
          <p class="job-note">{_esc(j['note'])}</p>
          {f'<p class="chips">{tags}</p>' if tags else ''}
          <ul>{bullets}</ul>
        </div>""")

    clients_html = " · ".join(
        f"<b>{_esc(c)}</b> <span style='color:#7a7a7a'>({_esc(CLIENT_META.get(c, ''))})</span>"
        for c in clients
    )

    skills_html = "".join(
        f"<li><b>{_esc(k)}:</b> {_esc(v)}</li>" for k, v in SKILLS
    )
    edu_html = "".join(
        f'<div class="edu-item"><b>{_esc(a)}</b><br><span>{_esc(b)}</span></div>'
        for a, b in EDU
    )

    role_line = role if not company else f"{role} · {company}"
    foot = (f'Полная версия резюме: <a href="{_esc(web_url)}">{_esc(web_url)}</a>'
            if web_url else "")

    doc = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"></head><body>
    <div class="name">Артемий Спасенов</div>
    <div class="role">{_esc(role_line)}</div>
    <div class="contacts">
      Москва · гибрид или удалёнка &nbsp;·&nbsp;
      +7 916 935-58-66 &nbsp;·&nbsp;
      <a href="https://t.me/Spasenov_Artemiy">@Spasenov_Artemiy</a> &nbsp;·&nbsp;
      <a href="mailto:spasionovartemiy@mail.ru">spasionovartemiy@mail.ru</a>
    </div>
    <div class="rule"></div>

    <section>
      <h2>Коротко</h2>
      <p class="lede">{_esc(content.get('tagline', ''))}</p>
      {f'<p class="chips" style="margin-top:5pt">{_chips(industries)}</p>' if industries else ''}
    </section>

    <section>
      <h2>Почему подхожу на эту роль</h2>
      <ul class="fit">{''.join(fit_items)}</ul>
    </section>

    <section>
      <h2>Опыт · 7 лет 9 месяцев</h2>
      {''.join(jobs_html)}
    </section>

    {f'<section><h2>Проекты для</h2><p class="clients">{clients_html}</p></section>' if clients_html else ''}

    <section>
      <h2>Навыки</h2>
      <ul>{skills_html}</ul>
    </section>

    <section>
      <h2>Образование и языки</h2>
      {edu_html}
      <div class="edu-item" style="margin-top:4pt">
        <b>Языки</b><br><span>Русский — родной · Английский — B2 · Испанский — B1</span>
      </div>
    </section>

    <div class="foot">
      {foot}{' &nbsp;·&nbsp; ' if foot else ''}Обновлено {dt.datetime.now().strftime('%d.%m.%Y')}
    </div>
    </body></html>"""

    HTML(string=doc).write_pdf(path, stylesheets=[CSS(string=CSS_TEXT)])
    log.info("PDF собран: %s", path)
    return path


def pdf_filename(slug):
    """analitik-figma -> Спасенов_Артемий_analitik-figma.pdf"""
    return f"Спасенов_Артемий_{slug}.pdf"

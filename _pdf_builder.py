"""
PDF-резюме на 1-2 страницы из того же контента, что и веб-версия.
Дополнительных запросов к модели не делает.

Раскладка: боковая колонка (фото, контакты, навыки, языки, образование)
и основная (профиль, ключевое, опыт, клиенты).
"""
import base64
import datetime as dt
import html
import logging
import os

from weasyprint import CSS, HTML

log = logging.getLogger("pdf")

PHOTO_PATH = os.getenv("PHOTO_PATH", "/app/photo.jpg")

CSS_TEXT = """
@page {
  size: A4; margin: 0;
  @bottom-right {
    content: counter(page) " / " counter(pages);
    font-family: "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: 7pt; color: #b0b0b0; margin: 0 14mm 7mm 0;
  }
}
* { box-sizing: border-box; }
body { font-family: "Noto Sans", "DejaVu Sans", sans-serif;
       font-size: 8.1pt; line-height: 1.36; color: #1c1c1c; margin: 0; }
a { color: #c2410c; text-decoration: none; }

.topbar { height: 5mm; background: #c2410c; }
.page { padding: 7mm 13mm 8mm 13mm; }

.head { margin-bottom: 5mm; }
.photo { width: 27mm; height: 27mm; border-radius: 13.5mm; float: left; margin-right: 7mm; }
.head h1 { font-size: 19pt; font-weight: bold; letter-spacing: -0.5pt;
           margin: 1mm 0 0 0; line-height: 1.05; }
.head .role { font-size: 10.5pt; color: #c2410c; font-weight: bold; margin: 1.5mm 0 0 0; }
.head .where { font-size: 8.2pt; color: #6e6e6e; margin: 1.5mm 0 0 0; }
.clearfix::after { content: ""; display: block; clear: both; }

.side { float: left; width: 52mm; padding-right: 7mm; border-right: 0.5pt solid #e2e2e2; }
.main { margin-left: 59mm; }

h2 { font-size: 7.2pt; text-transform: uppercase; letter-spacing: 1.2pt;
     color: #9a9a9a; font-weight: bold; margin: 0 0 2.5mm 0; }
.side section, .main section { margin-bottom: 4.4mm; }

.side .row { margin-bottom: 1.6mm; font-size: 8.2pt; }
.side .row b { display: block; color: #8a8a8a; font-size: 6.8pt;
               text-transform: uppercase; letter-spacing: 0.6pt; font-weight: bold; }
.skill { margin-bottom: 2.2mm; }
.skill b { display: block; font-size: 8.2pt; margin-bottom: 0.8mm; }
.skill span { font-size: 7.8pt; color: #5a5a5a; line-height: 1.4; }
.edu { margin-bottom: 1.9mm; }
.edu b { font-size: 8.2pt; display: block; }
.edu span { font-size: 7.5pt; color: #6e6e6e; }

.lede { margin: 0; font-size: 8.6pt; }
.chips { margin: 2.5mm 0 0 0; padding: 0; }
.chip { display: inline-block; border: 0.5pt solid #dcdcdc; border-radius: 6pt;
        padding: 0.6mm 2mm; margin: 0 1.4mm 1.4mm 0; font-size: 7.2pt; color: #5a5a5a; }
.chip-accent { border-color: #c2410c; color: #c2410c; }

.key { margin: 0; padding: 0; list-style: none; }
.key li { margin-bottom: 2mm; padding-left: 3.4mm; border-left: 1.4pt solid #c2410c; }
.key b { display: block; margin-bottom: 0.4mm; }
.key span { color: #4a4a4a; }

.job { margin-bottom: 3.6mm; }
.job-top { margin-bottom: 0.6mm; }
.job-dates { float: right; font-size: 7.6pt; color: #8a8a8a; padding-top: 0.8mm; }
.job-title { font-weight: bold; font-size: 9.6pt; }
.job-co { color: #c2410c; font-weight: bold; }
.job-note { color: #6e6e6e; font-size: 7.6pt; margin: 0 0 1.2mm 0; }
.job ul { margin: 0; padding-left: 0; list-style: none; }
.job li { margin-bottom: 0.5mm; padding-left: 3.2mm; text-indent: -3.2mm; }
.job li::before { content: "— "; color: #c4c4c4; }

.clients { font-size: 8.4pt; }
.clients b { color: #1c1c1c; }

.foot { clear: both; margin-top: 5mm; padding-top: 2.5mm;
        border-top: 0.5pt solid #e2e2e2; font-size: 7pt; color: #9a9a9a; }
"""


JOBS = [
    {
        "title": "Руководитель проектов",
        "company": "Tactise Group",
        "dates": "03.2024 — н. в.",
        "note": "Международная группа: HSE-консалтинг и трансформация культуры производственной безопасности. Офисы: Москва, Мумбаи, Дубай.",
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


def _photo_tag():
    """Фото как data-URI. Нет файла — собираем без него, не падаем."""
    try:
        with open(PHOTO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return '<img class="photo" src="data:image/jpeg;base64,%s" alt="">' % b64
    except Exception as e:
        log.warning("фото не подключилось (%s) — собираю без него", e)
        return ""


def _chips(items):
    out = []
    for i, it in enumerate(items):
        cls = "chip chip-accent" if i == 0 else "chip"
        out.append('<span class="%s">%s</span>' % (cls, _esc(it)))
    return "".join(out)


def build_pdf(path, role, company, content, web_url="",
              fit_title="Почему подхожу на эту роль"):
    key_items = "".join(
        '<li><b>%s</b><span>%s</span></li>' % (_esc(i.get("title", "")), _esc(i.get("text", "")))
        for i in content.get("fit", [])[:3]
    )

    exp_tags = content.get("exp_tags") or []
    industries = content.get("industries") or []
    clients = content.get("clients") or []

    jobs_html = []
    for i, j in enumerate(JOBS):
        tags = ('<p class="chips">%s</p>' % _chips(exp_tags[:4])) if i == 0 and exp_tags else ""
        bullets = "".join("<li>%s</li>" % _esc(b) for b in j["bullets"][:3])
        jobs_html.append("""
      <div class="job">
        <div class="job-top clearfix">
          <span class="job-dates">%s</span>
          <span class="job-title">%s</span> ·
          <span class="job-co">%s</span>
        </div>
        <p class="job-note">%s</p>
        %s
        <ul>%s</ul>
      </div>""" % (_esc(j["dates"]), _esc(j["title"]), _esc(j["company"]),
                   _esc(j["note"]), tags, bullets))

    clients_html = "".join(
        '<div class="edu"><b>%s</b><span>%s</span></div>' % (_esc(c), _esc(CLIENT_META.get(c, "")))
        for c in clients
    )
    skills_html = "".join(
        '<div class="skill"><b>%s</b><span>%s</span></div>' % (_esc(k), _esc(v))
        for k, v in SKILLS
    )
    edu_html = "".join(
        '<div class="edu"><b>%s</b><span>%s</span></div>' % (_esc(a), _esc(b))
        for a, b in EDU
    )
    role_line = role if not company else "%s · %s" % (role, company)
    foot = ('Полная версия: <a href="%s">%s</a> &nbsp;·&nbsp; ' % (_esc(web_url), _esc(web_url))
            if web_url else "")
    ind_chips = ('<p class="chips">%s</p>' % _chips(industries)) if industries else ""
    clients_block = ('<section><h2>Проекты для</h2>%s</section>'
                     % clients_html) if clients_html else ""

    doc = """<!DOCTYPE html><html lang="ru"><head><meta charset="utf-8"></head><body>
<div class="topbar"></div>
<div class="page">

  <div class="head clearfix">
    %s
    <h1>Артемий<br>Спасенов</h1>
    <p class="role">%s</p>
    <p class="where">Москва · гибрид или удалёнка · английский B2</p>
  </div>

  <div class="side">
    <section>
      <h2>Контакты</h2>
      <div class="row"><b>Телефон</b>+7 916 935-58-66</div>
      <div class="row"><b>Telegram</b><a href="https://t.me/Spasenov_Artemiy">@Spasenov_Artemiy</a></div>
      <div class="row"><b>Почта</b><a href="mailto:spasionovartemiy@mail.ru">spasionovartemiy@mail.ru</a></div>
    </section>
    %s
    <section><h2>Навыки</h2>%s</section>
    <section>
      <h2>Языки</h2>
      <div class="row">Русский — родной</div>
      <div class="row">Английский — B2</div>
      <div class="row">Испанский — B1</div>
    </section>
    <section><h2>Образование</h2>%s</section>
  </div>

  <div class="main">
    <section>
      <h2>Коротко</h2>
      <p class="lede">%s</p>
      %s
    </section>
    <section>
      <h2>%s</h2>
      <ul class="key">%s</ul>
    </section>
    <section>
      <h2>Опыт · 7 лет 9 месяцев</h2>
      %s
    </section>
  </div>

  <div class="foot">%sОбновлено %s</div>
</div>
</body></html>""" % (
        _photo_tag(), _esc(role_line), clients_block, skills_html, edu_html,
        _esc(content.get("tagline", "")), ind_chips,
        _esc(fit_title), key_items, "".join(jobs_html),
        foot, dt.datetime.now().strftime("%d.%m.%Y"))

    HTML(string=doc).write_pdf(path, stylesheets=[CSS(string=CSS_TEXT)])
    log.info("PDF собран: %s", path)
    return path


def pdf_filename(slug):
    return "Спасенов_Артемий_%s.pdf" % slug

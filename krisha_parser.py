"""
Парсер krisha.kz (Каскелен) — объявления и их фото.

Страницы отдельных объявлений krisha.kz закрывает от автоматических запросов
(ответ 403 «Доступ заблокирован»). Парсер эту защиту не обходит: после первого
отказа он берёт данные только из списка поиска — заголовок, цену, адрес,
краткое описание и главное фото в полном размере.

Установка:
    pip install playwright
    playwright install chromium

Запуск:
    python krisha_parser.py                      # продажа квартир, Каскелен, 3 страницы
    python krisha_parser.py --pages 10
    python krisha_parser.py --type arenda        # аренда
    python krisha_parser.py --what doma-dachi    # дома (по умолчанию kvartiry)
    python krisha_parser.py --limit 5            # не больше 5 объявлений
    python krisha_parser.py --no-download        # только ссылки на фото в CSV
    python krisha_parser.py --url "<любая ссылка поиска с фильтрами>"
    python krisha_parser.py --pages 1 --debug    # показать, почему нет фото

Результат:
    krisha_kaskelen.csv          — объявления + ссылки на фото
    photos/<id>/1.jpg, 2.jpg…    — фото
"""

import argparse
import asyncio
import csv
import os
import random
import re
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, urlunparse

from playwright.async_api import async_playwright

BASE = "https://krisha.kz"
DEBUG = False
CITY = "kaskelen"

FIELDS = ["id", "title", "price", "price_raw", "address", "date",
          "description", "url", "photos_count", "photos"]

# фото на krisha лежат на CDN вида *.kcdn.kz или *.kcdn.online,
# размер бывает в имени: 1-750x470.webp или 1-full.jpg
PHOTO_RE = re.compile(
    r"https?:(?:\\?/){2}[a-z0-9\-.]*kcdn\.[a-z]+(?:\\?/)[^\s\"'<>()]+?\.(?:jpe?g|webp|png)",
    re.I)
CDN_MARK = "kcdn."
SIZE_RE = re.compile(r"-(?:(\d+)x(\d+)|full)(?=\.\w+$)")
BLOCKED = "Доступ заблокирован"


def page_url(url: str, n: int) -> str:
    p = urlparse(url)
    q = parse_qs(p.query)
    if n > 1:
        q["page"] = [str(n)]
    else:
        q.pop("page", None)
    return urlunparse(p._replace(query=urlencode(q, doseq=True)))


def to_int(s: str):
    d = re.sub(r"\D", "", s or "")
    return int(d) if d else None


def best_photos(urls) -> list[str]:
    """Одно фото = одна ссылка, самый большой размер, порядок сохраняется."""
    groups = {}
    for u in urls:
        u = u.replace("\\/", "/")
        m = SIZE_RE.search(u)
        # одно и то же фото отдаётся в .webp и .jpg — расширение в ключ не входит
        key = os.path.splitext(SIZE_RE.sub("", u))[0]
        area = int(m.group(1)) * int(m.group(2)) if m and m.group(1) else 10**9
        if key not in groups or area > groups[key][0]:
            groups[key] = (area, u)
    # отбрасываем явные миниатюры/иконки, но если остались только маленькие,
    # лучше показать их, чем ничего
    big = [u for a, u in groups.values() if a >= 200 * 150]
    return big or [u for a, u in groups.values()]


async def txt(el, sel: str) -> str:
    n = await el.query_selector(sel)
    return " ".join((await n.inner_text()).split()) if n else ""


async def parse_list(page) -> list[dict]:
    try:
        await page.wait_for_selector("div.a-card[data-id]", timeout=15000)
    except Exception:
        return []
    rows = []
    for card in await page.query_selector_all("div.a-card[data-id]"):
        link = await card.query_selector("a.a-card__title")
        href = await link.get_attribute("href") if link else ""
        stats = [" ".join((await s.inner_text()).split())
                 for s in await card.query_selector_all(".a-card__stats-item")]
        price_raw = await txt(card, ".a-card__price")
        thumbs = await card.evaluate("""c => [...c.querySelectorAll('picture,img,source')]
            .flatMap(e => ['data-full-src','src','data-src','srcset','data-srcset']
              .map(a => e.getAttribute(a) || ''))
            .flatMap(v => v.split(/[\\s,]+/))
            .filter(v => v.includes('kcdn.'))""")
        rows.append({
            "id": await card.get_attribute("data-id"),
            "title": await txt(card, "a.a-card__title"),
            "price": to_int(price_raw),
            "price_raw": price_raw,
            "address": await txt(card, ".a-card__subtitle"),
            "date": stats[1] if len(stats) > 1 else "",
            "description": await txt(card, ".a-card__text-preview"),
            "url": urljoin(BASE, href or ""),
            "thumbs": thumbs,
        })
    return rows


async def get_photos(page, url: str) -> list[str] | None:
    """Все фото со страницы объявления: из атрибутов галереи + из сырого HTML/JSON.

    None — сайт закрыл страницу от автоматических запросов.
    """
    resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if (resp and resp.status == 403) or BLOCKED in await page.title():
        return None
    try:
        await page.wait_for_selector(".gallery, .offer__gallery, [data-photo-url]",
                                     timeout=8000)
    except Exception:
        pass
    attrs = await page.evaluate("""() => {
        const out = [];
        document.querySelectorAll('[data-photo-url],[data-href],[data-src],img,source')
          .forEach(e => {
            for (const a of ['data-photo-url','data-href','data-src','src','srcset'])
              { const v = e.getAttribute(a); if (v) out.push(...v.split(/[\\s,]+/)); }
          });
        return out;
    }""")
    html = await page.content()
    found = [u for u in attrs if CDN_MARK in u] + PHOTO_RE.findall(html)
    if DEBUG:
        print(f"    [debug] заголовок: {await page.title()!r} | '{CDN_MARK}' в HTML: "
              f"{html.count(CDN_MARK)} | найдено ссылок: {len(found)}")
    return best_photos(found)


async def download(ctx, ad_id: str, urls: list[str], folder="photos"):
    path = os.path.join(folder, str(ad_id))
    os.makedirs(path, exist_ok=True)
    ok = 0
    names = [f"{i}{os.path.splitext(urlparse(u).path)[1] or '.jpg'}"
             for i, u in enumerate(urls, 1)]
    # файлы от прошлого запуска, которых в новом наборе нет, иначе попадут в импорт
    for old in os.listdir(path):
        if old not in names:
            os.remove(os.path.join(path, old))
    for u, name in zip(urls, names):
        fn = os.path.join(path, name)
        if os.path.exists(fn):
            ok += 1
            continue
        try:
            r = await ctx.request.get(u, headers={"Referer": BASE + "/"})
            if r.ok:
                with open(fn, "wb") as f:
                    f.write(await r.body())
                ok += 1
        except Exception as e:
            print("    не скачалось:", u, e)
    return ok


async def main(a):
    url = a.url or f"{BASE}/{a.type}/{a.what}/{CITY}/"
    seen, result = set(), []

    try:
        await crawl(a, url, seen, result)
    finally:
        # пишем и при сбое или Ctrl+C, чтобы собранное не пропало
        with open(a.out, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(result)
        total = sum(r["photos_count"] for r in result)
        print(f"Готово: {len(result)} объявлений, {total} фото → {a.out}")


async def crawl(a, url, seen, result):
    details = True  # пока сайт отдаёт страницы объявлений
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not a.show)
        ctx = await browser.new_context(
            locale="ru-RU",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/130.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900},
        )
        # в браузере картинки не грузим (быстрее); скачиваем отдельно через ctx.request
        await ctx.route("**/*", lambda r: r.abort()
                        if r.request.resource_type in ("image", "media", "font")
                        else r.continue_())
        page = await ctx.new_page()

        for n in range(1, a.pages + 1):
            u = page_url(url, n)
            print(f"[стр. {n}/{a.pages}] {u}")
            try:
                await page.goto(u, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                print("  ошибка:", e)
                continue

            rows = [r for r in await parse_list(page) if r["id"] not in seen]
            if DEBUG:
                print(f"  [debug] заголовок списка: {await page.title()!r}, карточек: {len(rows)}")
            if not rows:
                print("  объявлений больше нет — стоп")
                break
            seen.update(r["id"] for r in rows)
            if a.limit:
                rows = rows[:a.limit - len(result)]

            for r in rows:
                ph = []
                if details:
                    try:
                        ph = await get_photos(page, r["url"])
                    except Exception as e:
                        print(f"  {r['id']}: ошибка фото — {e}")
                    if ph is None:
                        details = False
                        ph = []
                        print("  сайт закрыл страницы объявлений (403) — "
                              "дальше берём данные и главное фото из списка")
                if not ph and r["thumbs"]:
                    # со страницы объявления ничего не пришло: берём фото из карточки списка
                    ph = best_photos(r["thumbs"])
                r["photos"] = " | ".join(ph)
                r["photos_count"] = len(ph)
                msg = f"  {r['id']}: {len(ph)} фото"
                if ph and not a.no_download:
                    msg += f", скачано {await download(ctx, r['id'], ph)}"
                print(msg)
                r.pop("thumbs", None)
                result.append(r)
                await asyncio.sleep(random.uniform(1.0, 2.5))

            if a.limit and len(result) >= a.limit:
                break
            await asyncio.sleep(random.uniform(1.5, 3.5))

        await browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="krisha.kz Каскелен — объявления и фото")
    ap.add_argument("--type", default="prodazha", choices=["prodazha", "arenda"])
    ap.add_argument("--what", default="kvartiry",
                    help="kvartiry | doma-dachi | uchastkov | kommercheskaya-nedvizhimost")
    ap.add_argument("--url", help="своя ссылка поиска (перекрывает --type/--what)")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0, help="не больше стольких объявлений")
    ap.add_argument("--out", default="krisha_kaskelen.csv")
    ap.add_argument("--no-download", action="store_true", help="не скачивать, только ссылки")
    ap.add_argument("--show", action="store_true", help="показать браузер")
    ap.add_argument("--debug", action="store_true", help="печатать, что видно на страницах")
    args = ap.parse_args()
    DEBUG = args.debug
    asyncio.run(main(args))

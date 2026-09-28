# -*- coding: utf-8 -*-
r"""build_feed.py — сборка фида Авито Автозагрузки из items.json (канон проекта «Резина»).

По умолчанию DRY-RUN: собирает feed.xml локально и печатает сводку. Ничего не отправляет.
  python build_feed.py                 # собрать все позиции → feed.xml
  python build_feed.py --only 6 15     # только указанные №
  python build_feed.py --push          # + закоммитить и отправить в GitHub (Авито читает raw-ссылку)
  python build_feed.py --push --upload # + запустить загрузку через API Авито (не чаще раза в час)
  python build_feed.py --status        # показать текущую загрузку и ошибки по объявлениям

Ключи API — D:\Проекты Claud\_secrets\avito.json. Категории: «Легковые шины» (type=tires)
и «Колёса» (type=wheels, нужны rim_type/rim_width/rim_offset/rim_bolts/rim_pcd/rim_dia).
"""
import sys, os, json, argparse, subprocess, urllib.request, urllib.parse
sys.stdout.reconfigure(encoding="utf-8")
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
NO_PRICE = False   # --no-price: пробная загрузка без цены (Авито проверит всё, но не опубликует)
SECRETS = r"D:\Проекты Claud\_secrets\avito.json"
API = "https://api.avito.ru"


def token():
    s = json.load(open(SECRETS, encoding="utf-8"))
    data = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": s["client_id"], "client_secret": s["client_secret"]}).encode()
    return json.load(urllib.request.urlopen(urllib.request.Request(f"{API}/token", data=data)))["access_token"]


def api(path, method="GET", body=None, tok=None):
    req = urllib.request.Request(f"{API}{path}", method=method, headers={"Authorization": f"Bearer {tok or token()}", "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


def photos_for(num, base):
    d = os.path.join(HERE, "photos", str(num))
    if not os.path.isdir(d):
        return []
    return [f"{base}/{num}/{f}" for f in sorted(os.listdir(d)) if f.lower().endswith((".jpg", ".jpeg"))][:10]


def tag(name, val):
    return f"    <{name}>{escape(str(val))}</{name}>\n" if val not in (None, "") else ""


def build(items, common):
    out = ['<?xml version="1.0" encoding="UTF-8"?>\n<Ads formatVersion="3" target="Avito">\n']
    problems = []
    for it in items:
        n = it["id"]; wheels = it["type"] == "wheels"
        a = f"  <Ad>\n" + tag("Id", f"rezina-{n:02d}")
        a += tag("Category", "Запчасти и аксессуары") + tag("GoodsType", "Шины, диски и колёса")
        a += tag("ProductType", "Колёса" if wheels else "Легковые шины")
        a += tag("AdType", "Товар приобретен на продажу") + tag("Condition", "Б/у")
        a += tag("Title", it["title"]) + ("" if NO_PRICE else tag("Price", it["price"]))
        a += tag("Brand", it["brand"]) + tag("Model", it["model"])
        a += tag("TireSectionWidth", it["width"]) + tag("TireAspectRatio", it["aspect"]) + tag("RimDiameter", it["rim"])
        a += tag("TireType", it["season"]) + tag("Quantity", f"за {it['qty']} шт.")
        a += tag("TireYear", it["year"]) + tag("ResidualTread", it["tread"])
        a += tag("TireRuptureQuantity", it["rupture"]) + tag("TireSideRepairQuantity", it["repair"]) + tag("OtherDefects", it["defects"])
        if it.get("different_width"):
            a += tag("DifferentWidthTires", "Да") + tag("BackTireSectionWidth", it["back_width"]) + tag("BackTireAspectRatio", it["back_aspect"]) + tag("BackRimDiameter", it["back_rim"])
        else:
            a += tag("DifferentWidthTires", "Нет")
        if wheels:
            for k, t in [("rim_type", "RimType"), ("rim_width", "RimWidth"), ("rim_offset", "RimOffset"), ("rim_bolts", "RimBolts"), ("rim_pcd", "RimBoltsDiameter"), ("rim_dia", "RimDIA")]:
                if it.get(k) in (None, ""):
                    problems.append(f"№{n}: нет параметра диска {k} ({t}) — обязателен для «Колёс»")
                a += tag(t, it.get(k))
        a += tag("Address", common["address"]) + tag("ContactPhone", common["phone"])
        a += f"    <Description><![CDATA[{it['text']}]]></Description>\n"
        ph = photos_for(n, common["photo_base"])
        if not ph:
            problems.append(f"№{n}: нет фото в photos/{n}")
        a += "    <Images>\n" + "".join(f'      <Image url="{u}"/>\n' for u in ph) + "    </Images>\n"
        a += "  </Ad>\n"
        out.append(a)
        if len(it["title"]) > 50:
            problems.append(f"№{n}: заголовок {len(it['title'])} знаков (>50)")
    out.append("</Ads>\n")
    return "".join(out), problems


def status(tok):
    code, cur = api("/autoload/v4/uploads/current", tok=tok)
    print("Текущая загрузка:", json.dumps(cur, ensure_ascii=False)[:600])
    code, items = api("/autoload/v4/uploads/current/items?perPage=50", tok=tok)
    for i in (items or {}).get("items", []):
        print(f"\n{i['ad_id']}: {i['section']['title']}")
        for m in i.get("messages", []):
            print(f"   [{m['type']}] {m['title']}")
        if i.get("url"):
            print("   ", i["url"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="*", type=int, help="только эти №")
    p.add_argument("--push", action="store_true", help="коммит и push в GitHub")
    p.add_argument("--upload", action="store_true", help="запустить загрузку через API Авито")
    p.add_argument("--status", action="store_true", help="показать отчёт по текущей загрузке")
    p.add_argument("--no-price", action="store_true", help="пробный фид без цены — ничего не публикуется")
    args = p.parse_args()
    global NO_PRICE; NO_PRICE = args.no_price
    if args.status:
        status(token()); return
    d = json.load(open(os.path.join(HERE, "items.json"), encoding="utf-8"))
    items = [i for i in d["items"] if not args.only or i["id"] in args.only]
    xml, problems = build(items, d["common"])
    open(os.path.join(HERE, "feed.xml"), "w", encoding="utf-8", newline="\n").write(xml)
    print(f"feed.xml: {len(items)} объявлений, {len(xml)} байт")
    for i in items:
        print(f"  №{i['id']:>2} {'колёса' if i['type']=='wheels' else 'шины  '} {i['price']:>6} ₽  фото {len(photos_for(i['id'], d['common']['photo_base']))}  {i['title']}")
    for pr in problems:
        print("  ⚠", pr)
    if not args.push:
        print("DRY-RUN: ничего не отправлено. Для публикации: --push [--upload]"); return
    if problems:
        print("Есть проблемы выше — push отменён."); sys.exit(1)
    subprocess.run(["git", "add", "-A"], cwd=HERE, check=True)
    subprocess.run(["git", "-c", "user.name=Dmitry", "-c", "user.email=gptfor896@gmail.com", "commit", "-qm",
                    f"Фид: {len(items)} объявлений\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"], cwd=HERE)
    subprocess.run(["git", "push", "-q"], cwd=HERE, check=True)
    print("Отправлено в GitHub.")
    if args.upload:
        code, r = api("/autoload/v1/upload", "POST", {})
        print("Запуск загрузки Авито:", code, r)


if __name__ == "__main__":
    main()

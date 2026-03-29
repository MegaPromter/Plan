"""
Нарезает zoom-фрагменты из полноразмерных скриншотов.
Sidebar ~255px, top nav ~55px, content starts at ~(255, 60).
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os

SCREENSHOTS = Path(__file__).parent / "screenshots"
CROPS = Path(__file__).parent / "screenshots" / "crops"
CROPS.mkdir(exist_ok=True)

FONT_PATH = None
for candidate in [
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/arial.ttf",
]:
    if os.path.exists(candidate):
        FONT_PATH = candidate
        break


def get_font(size):
    if FONT_PATH:
        return ImageFont.truetype(FONT_PATH, size)
    return ImageFont.load_default()


def crop_save(src, dst, box, scale=1.0):
    img = Image.open(SCREENSHOTS / src)
    c = img.crop(box)
    if scale != 1.0:
        c = c.resize((int(c.width * scale), int(c.height * scale)), Image.LANCZOS)
    c.save(CROPS / dst, quality=95)
    print(f"  {dst}: {c.size[0]}x{c.size[1]}")
    return c


def label(img, text, pos, color=(26, 115, 232), size=24):
    draw = ImageDraw.Draw(img)
    font = get_font(size)
    bb = draw.textbbox(pos, text, font=font)
    draw.rectangle([bb[0]-4, bb[1]-3, bb[2]+4, bb[3]+3], fill=(255, 255, 255))
    draw.text(pos, text, fill=color, font=font)
    return img


def rect(img, box, color=(255, 68, 68), width=3):
    ImageDraw.Draw(img).rectangle(box, outline=color, width=width)
    return img


def arrow_line(img, start, end, color=(255, 68, 68), width=2):
    ImageDraw.Draw(img).line([start, end], fill=color, width=width)
    return img


def make_annotated_full(src, dst, annotations):
    """Copy full screenshot, add annotation boxes + labels with lines."""
    img = Image.open(SCREENSHOTS / src).copy()
    for ann in annotations:
        box = ann.get("box")
        lbl = ann.get("label")
        lpos = ann.get("label_pos")
        col = ann.get("color", (255, 68, 68))
        if box:
            rect(img, box, color=col, width=3)
        if lbl and lpos:
            label(img, lbl, lpos, color=col, size=ann.get("font_size", 22))
            # line from label to box center
            if box:
                box_cx = (box[0] + box[2]) // 2
                box_cy = (box[1] + box[3]) // 2
                bb = ImageDraw.Draw(img).textbbox(lpos, lbl, font=get_font(ann.get("font_size", 22)))
                lbl_cx = (bb[0] + bb[2]) // 2
                lbl_cy = bb[3] + 5
                arrow_line(img, (lbl_cx, lbl_cy), (box_cx, box_cy), color=col)
    img.save(CROPS / dst, quality=95)
    print(f"  {dst}: {img.size[0]}x{img.size[1]} (annotated)")
    return img


def make_all():
    print("Нарезка фрагментов...")

    # ===== PP TABLE =====
    # Full annotated PP
    make_annotated_full("pp_table.png", "pp_table_annotated.png", [
        {"box": (255, 58, 950, 85), "label": "① Статусная панель",
         "label_pos": (960, 60), "color": (255, 68, 68)},
        {"box": (255, 85, 1600, 115), "label": "② Панель инструментов",
         "label_pos": (1100, 86), "color": (34, 168, 83)},
        {"box": (255, 115, 1920, 145), "label": "③ Заголовки + фильтры",
         "label_pos": (1400, 116), "color": (26, 115, 232)},
    ])

    # Status panel zoom
    c = crop_save("pp_table.png", "pp_status_panel.png", (255, 58, 950, 88), scale=3.0)
    label(c, "Все · Выполнено · Просрочено · В работе", (10, 10), size=20)
    c.save(CROPS / "pp_status_panel.png")

    # Toolbar zoom
    c = crop_save("pp_table.png", "pp_toolbar.png", (255, 85, 1600, 115), scale=3.0)
    label(c, "Поиск | Добавить строку | Синхронизация | Статистика | Промилле", (10, 10), size=18)
    c.save(CROPS / "pp_toolbar.png")

    # Headers + filter buttons
    crop_save("pp_table.png", "pp_headers.png", (255, 115, 1920, 150), scale=3.0)

    # Data rows
    crop_save("pp_table.png", "pp_rows_zoom.png", (255, 145, 1920, 380), scale=1.5)

    # ===== PLAN TABLE (SP) =====
    make_annotated_full("plan_table.png", "sp_table_annotated.png", [
        {"box": (255, 58, 780, 80), "label": "① Статусная панель",
         "label_pos": (800, 60), "color": (255, 68, 68)},
        {"box": (255, 20, 1500, 55), "label": "② Тулбар (+ Задача, Ошибки, Плотность, Столбцы)",
         "label_pos": (800, 2), "color": (34, 168, 83)},
        {"box": (255, 80, 1920, 120), "label": "③ Заголовки с фильтрами",
         "label_pos": (1400, 78), "color": (26, 115, 232)},
    ])

    # SP rows with monthly hours zoom
    crop_save("plan_table.png", "sp_rows_zoom.png", (255, 120, 1920, 400), scale=1.3)

    # ===== DASHBOARD =====
    make_annotated_full("dashboard.png", "dash_annotated.png", [
        {"box": (300, 55, 1640, 95), "label": "① Переключатель периода",
         "label_pos": (1100, 38), "color": (255, 68, 68)},
        {"box": (300, 95, 1640, 220), "label": "② Карточки показателей",
         "label_pos": (1100, 222), "color": (34, 168, 83)},
        {"box": (300, 240, 1640, 510), "label": "③ Блок Команда",
         "label_pos": (1100, 510), "color": (26, 115, 232)},
    ])

    # Metrics cards zoom
    c = crop_save("dashboard.png", "dash_metrics.png", (300, 95, 1640, 220), scale=1.8)
    c.save(CROPS / "dash_metrics.png")

    # Team block zoom
    crop_save("dashboard.png", "dash_team.png", (300, 240, 1640, 510), scale=1.3)

    # ===== NOTICES =====
    make_annotated_full("notices.png", "notices_annotated.png", [
        {"box": (255, 35, 1920, 65), "label": "Заголовки столбцов",
         "label_pos": (1500, 18), "color": (26, 115, 232)},
        {"box": (1830, 60, 1915, 500), "label": "Статусы (цветовые)",
         "label_pos": (1650, 500), "color": (255, 68, 68)},
    ])

    # Notices rows zoom
    crop_save("notices.png", "notices_rows.png", (255, 55, 1920, 350), scale=1.3)

    # ===== ANALYTICS =====
    make_annotated_full("analytics.png", "analytics_annotated.png", [
        {"box": (300, 80, 1500, 130), "label": "① Карточки-итоги",
         "label_pos": (1100, 62), "color": (255, 68, 68)},
        {"box": (300, 130, 1500, 370), "label": "② Графики загрузки",
         "label_pos": (1100, 372), "color": (34, 168, 83)},
        {"box": (300, 390, 1500, 540), "label": "③ Таблица по отделам",
         "label_pos": (1100, 540), "color": (26, 115, 232)},
    ])

    # Chart zoom
    crop_save("analytics.png", "analytics_chart.png", (300, 130, 1500, 370), scale=1.5)

    # ===== WORK CALENDAR =====
    make_annotated_full("work_calendar.png", "cal_annotated.png", [
        {"box": (255, 30, 800, 280), "label": "① Сводная таблица часов",
         "label_pos": (810, 100), "color": (255, 68, 68)},
        {"box": (255, 290, 1920, 540), "label": "② Мини-календари",
         "label_pos": (1000, 545), "color": (34, 168, 83)},
    ])

    # Mini calendars zoom
    crop_save("work_calendar.png", "cal_mini.png", (255, 290, 1920, 540), scale=1.3)

    # ===== EMPLOYEES =====
    make_annotated_full("employees.png", "emp_annotated.png", [
        {"box": (255, 30, 900, 75), "label": "Поиск и фильтрация",
         "label_pos": (910, 40), "color": (255, 68, 68)},
    ])
    crop_save("employees.png", "emp_roles.png", (255, 75, 900, 450), scale=1.5)

    # ===== PROFILE =====
    make_annotated_full("profile.png", "profile_annotated.png", [
        {"box": (300, 45, 850, 300), "label": "① Карточка пользователя",
         "label_pos": (860, 100), "color": (255, 68, 68)},
        {"box": (300, 310, 850, 550), "label": "② Моё меню (настройки)",
         "label_pos": (860, 400), "color": (34, 168, 83)},
    ])

    # My menu zoom
    crop_save("profile.png", "profile_menu.png", (300, 310, 850, 550), scale=1.8)

    # ===== COMMAND PALETTE =====
    crop_save("command_palette.png", "cmd_zoom.png", (550, 180, 1370, 550), scale=1.5)

    # ===== PROJECTS =====
    crop_save("projects.png", "proj_card.png", (270, 80, 680, 340), scale=2.0)

    # ===== LOGIN =====
    crop_save("login.png", "login_form.png", (620, 220, 1300, 680), scale=1.5)

    # ===== TOUR =====
    crop_save("tour_step.png", "tour_card.png", (50, 85, 700, 280), scale=2.0)

    print(f"\nГотово! {len(list(CROPS.glob('*.png')))} фрагментов")


if __name__ == '__main__':
    make_all()

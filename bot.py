import logging
import json
import os
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SPREADSHEET_ID = "1V2QRGQEGj3jiXhBAFUTnm8wHxDHGihdr"
BOT_TOKEN = os.getenv("BOT_TOKEN", "7694310665:AAFVYZBpSLTQZ-gRIE40AU9bdT5YFZkl1bE")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_sheet():
    creds_json = os.getenv("GOOGLE_CREDENTIALS")
    if creds_json:
        creds_dict = json.loads(creds_json)
    else:
        with open("credentials.json") as f:
            creds_dict = json.load(f)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)

# ── Категорії бюджету (назва → рядок в таблиці)
BUDGET_CATEGORIES = {
    "оренда":     ("📊 Бюджет квітня", "оренда житла"),
    "рент":       ("📊 Бюджет квітня", "оренда житла"),
    "світло":     ("📊 Бюджет квітня", "електрика"),
    "чинш":       ("📊 Бюджет квітня", "чинш"),
    "ровер":      ("📊 Бюджет квітня", "оренда ровера"),
    "велик":      ("📊 Бюджет квітня", "оренда ровера"),
    "їжа":        ("📊 Бюджет квітня", "їжа"),
    "продукти":   ("📊 Бюджет квітня", "їжа"),
    "ресторан":   ("📊 Бюджет квітня", "ресторани"),
    "кафе":       ("📊 Бюджет квітня", "ресторани"),
    "телефон":    ("📊 Бюджет квітня", "зв'язок"),
    "зв'язок":    ("📊 Бюджет квітня", "зв'язок"),
    "покупки":    ("📊 Бюджет квітня", "покупки"),
    "послуги":    ("📊 Бюджет квітня", "послуги"),
    "здоров'я":   ("📊 Бюджет квітня", "здоров'я"),
    "покер":      ("📊 Бюджет квітня", "покер"),
    "борги":      ("📊 Бюджет квітня", "на борги"),
}

DEBT_ALIASES = {
    "а": "Містер A", "a": "Містер A",
    "б": "Містер B", "b": "Містер B",
    "в": "Містер C", "c": "Містер C",
    "г": "Містер D", "d": "Містер D",
    "д": "Містер E", "e": "Містер E",
    "е": "Містер F", "f": "Містер F",
    "мандати": "Мандати (штрафи дорожні)",
    "штрафи":  "Мандати (штрафи дорожні)",
    "зус":     "ZUS (соціальне страхування)",
    "zus":     "ZUS (соціальне страхування)",
    "податки": "Податки (Urząd Skarbowy)",
    "суд":     "Судові оплати / Sąd",
}

MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["💸 Витрата", "💰 Сплатив борг"],
    ["📊 Бюджет", "💸 Борги"],
    ["🃏 Покер сесія", "❓ Допомога"],
], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт Микола!\n\n"
        "Я твій бюджетний бот. Все що вписуєш — летить прямо в Google Sheets.\n\n"
        "Швидкі команди:\n"
        "💸 /витрата їжа 150\n"
        "💰 /борг а 200\n"
        "🃏 /покер 50 80 (бай-ін результат)\n"
        "📊 /бюджет — переглянути залишки\n"
        "💸 /борги — переглянути всі борги",
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📋 *Команди:*\n\n"
        "*Витрати:*\n"
        "`/витрата їжа 150` — записати витрату\n"
        "`/витрата покер 200`\n"
        "`/витрата оренда 2000`\n\n"
        "*Борги:*\n"
        "`/борг а 500` — сплатив Містеру A\n"
        "`/борг мандати 300`\n"
        "`/борг зус 200`\n\n"
        "*Покер:*\n"
        "`/покер 50 120` — бай-ін 50, результат 120\n\n"
        "*Перегляд:*\n"
        "`/бюджет` — залишки по категоріях\n"
        "`/борги` — всі борги\n\n"
        "*Категорії витрат:*\n"
        "їжа, продукти, ресторан, кафе,\n"
        "оренда, рент, світло, чинш,\n"
        "ровер, велик, телефон, покупки,\n"
        "послуги, здоров'я, покер, борги"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

def find_row_by_keyword(worksheet, keyword):
    """Знайти рядок в таблиці по ключовому слову"""
    all_values = worksheet.get_all_values()
    keyword_lower = keyword.lower()
    for i, row in enumerate(all_values):
        if row and keyword_lower in row[0].lower():
            return i + 1  # 1-indexed
    return None

async def vitrata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Записати витрату: /витрата категорія сума"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Формат: `/витрата категорія сума`\n"
            "Приклад: `/витрата їжа 150`",
            parse_mode="Markdown"
        )
        return

    category_input = context.args[0].lower()
    try:
        amount = float(context.args[1].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Сума має бути числом. Приклад: `/витрата їжа 150`", parse_mode="Markdown")
        return

    # знайти категорію
    matched = None
    for key, val in BUDGET_CATEGORIES.items():
        if key in category_input or category_input in key:
            matched = val
            break

    if not matched:
        await update.message.reply_text(
            f"❓ Не знаю категорію *{category_input}*\n"
            "Спробуй: їжа, оренда, покер, ресторан, ровер, світло...",
            parse_mode="Markdown"
        )
        return

    sheet_name, keyword = matched

    try:
        sheet = get_sheet()
        ws = sheet.worksheet(sheet_name)
        row_num = find_row_by_keyword(ws, keyword)

        if not row_num:
            await update.message.reply_text(f"❌ Не знайшов рядок '{keyword}' в таблиці")
            return

        # Колонка C = витрачено (3)
        current = ws.cell(row_num, 3).value
        try:
            current_val = float(str(current).replace(" ", "").replace("zł", "").replace(",", ".")) if current else 0
        except:
            current_val = 0

        new_val = current_val + amount
        ws.update_cell(row_num, 3, new_val)

        # отримати ліміт для порівняння
        limit = ws.cell(row_num, 2).value
        try:
            limit_val = float(str(limit).replace(" ", "").replace("zł", "").replace(",", ".")) if limit else 0
        except:
            limit_val = 0

        remaining = limit_val - new_val
        status = "✅ В межах" if remaining >= 0 else f"🔴 Перевитрата на {abs(remaining):.0f} zł"

        await update.message.reply_text(
            f"✅ *Записано!*\n\n"
            f"📂 Категорія: {keyword.capitalize()}\n"
            f"💸 Додано: {amount:.0f} zł\n"
            f"📊 Всього витрачено: {new_val:.0f} zł\n"
            f"💰 Ліміт: {limit_val:.0f} zł\n"
            f"📉 Залишок: {remaining:.0f} zł\n"
            f"{'✅ В межах' if remaining >= 0 else '🔴 Перевитрата!'}",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def bory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Записати оплату боргу: /борг а 200"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Формат: `/борг кому сума`\n"
            "Приклад: `/борг а 200` або `/борг мандати 300`",
            parse_mode="Markdown"
        )
        return

    who_input = context.args[0].lower()
    try:
        amount = float(context.args[1].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Сума має бути числом")
        return

    # знайти кому
    debt_name = DEBT_ALIASES.get(who_input)
    if not debt_name:
        await update.message.reply_text(
            f"❓ Не знаю *{who_input}*\n"
            "Використовуй: а, б, в, г, д, е або мандати, зус, податки, суд",
            parse_mode="Markdown"
        )
        return

    try:
        sheet = get_sheet()
        ws = sheet.worksheet("💸 Борги")
        row_num = find_row_by_keyword(ws, debt_name[:10])

        if not row_num:
            await update.message.reply_text(f"❌ Не знайшов рядок для '{debt_name}'")
            return

        # Колонка F = вже сплачено (6)
        current = ws.cell(row_num, 6).value
        try:
            current_val = float(str(current).replace("$", "").replace(",", ".").strip()) if current else 0
        except:
            current_val = 0

        new_val = current_val + amount
        ws.update_cell(row_num, 6, new_val)

        # залишок = E - F
        total_debt = ws.cell(row_num, 5).value
        try:
            total_val = float(str(total_debt).replace("$", "").replace(",", ".").strip()) if total_debt else 0
        except:
            total_val = 0

        remaining = total_val - new_val

        await update.message.reply_text(
            f"✅ *Оплату записано!*\n\n"
            f"👤 Кому: {debt_name}\n"
            f"💰 Сплачено зараз: ${amount:.2f}\n"
            f"📊 Всього сплачено: ${new_val:.2f}\n"
            f"💸 Залишок боргу: ${remaining:.2f}\n"
            f"{'🎉 Борг закрито!' if remaining <= 0 else ''}",
            parse_mode="Markdown"
        )

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def poker_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Записати покер сесію: /покер бай-ін результат"""
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Формат: `/покер бай-ін результат`\n"
            "Приклад: `/покер 50 120` (купив за $50, вийшов з $120)",
            parse_mode="Markdown"
        )
        return

    try:
        buy_in = float(context.args[0].replace(",", "."))
        result = float(context.args[1].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Вкажи числа. Приклад: `/покер 50 120`", parse_mode="Markdown")
        return

    pl = result - buy_in
    pl_text = f"+${pl:.2f}" if pl >= 0 else f"-${abs(pl):.2f}"

    # перевірка стоп-лос
    warnings = []
    if pl <= -buy_in * 2:
        warnings.append("🔴 СТОП-ЛОС! Мінус 2+ бай-іни. Виходь!")
    if pl >= buy_in * 3:
        warnings.append("🟢 СТОП-ВІН! Плюс 3+ бай-іни. Фіксуй!")

    try:
        sheet = get_sheet()
        ws = sheet.worksheet("🃏 Покер трекер")
        all_values = ws.get_all_values()

        # знайти перший порожній рядок (з 4-го)
        empty_row = None
        for i in range(3, len(all_values)):
            if not all_values[i][0]:
                empty_row = i + 1
                break

        if not empty_row:
            empty_row = len(all_values) + 1

        today = datetime.now().strftime("%d.%m")
        ws.update_cell(empty_row, 1, today)           # Дата
        ws.update_cell(empty_row, 3, buy_in)           # Бай-ін
        ws.update_cell(empty_row, 4, result)           # Результат
        # П/Л рахується формулою автоматично
        ws.update_cell(empty_row, 6, "Так" if buy_in <= 50 else "Ні")  # BRM
        ws.update_cell(empty_row, 7, "Так" if pl > -buy_in * 2 else "Ні")  # Стоп-лос

        msg = (
            f"🃏 *Сесію записано!*\n\n"
            f"📅 Дата: {today}\n"
            f"💵 Бай-ін: ${buy_in:.2f}\n"
            f"📤 Вийшов з: ${result:.2f}\n"
            f"{'🟢' if pl >= 0 else '🔴'} П/Л: {pl_text}\n"
        )
        if warnings:
            msg += "\n" + "\n".join(warnings)

        await update.message.reply_text(msg, parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def show_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати залишки бюджету"""
    try:
        sheet = get_sheet()
        ws = sheet.worksheet("📊 Бюджет квітня")
        all_values = ws.get_all_values()

        lines = ["📊 *БЮДЖЕТ КВІТНЯ*\n"]
        for row in all_values[3:]:  # з 4-го рядка
            if not row[0] or row[0].startswith("─") or row[0].startswith("РА") or row[0].startswith("💵"):
                continue
            if len(row) >= 4:
                cat = row[0].strip()
                limit = row[1].strip()
                spent = row[2].strip()
                remaining = row[3].strip()
                if cat and limit:
                    try:
                        r = float(remaining.replace("zł","").replace(",",".").replace(" ","")) if remaining else 0
                        emoji = "✅" if r >= 0 else "🔴"
                        lines.append(f"{emoji} {cat[:20]}: {spent} / {limit}")
                    except:
                        lines.append(f"• {cat[:25]}: {spent} / {limit}")

        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def show_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати всі борги"""
    try:
        sheet = get_sheet()
        ws = sheet.worksheet("💸 Борги")
        all_values = ws.get_all_values()

        lines = ["💸 *МОЇ БОРГИ*\n"]
        total = 0
        for row in all_values[3:]:
            if not row[0] or not row[0].strip().isdigit():
                continue
            if len(row) >= 7:
                pseudo = row[2].strip()
                dtype = row[3].strip()
                debt = row[4].strip()
                paid = row[5].strip()
                remaining = row[6].strip()
                try:
                    r = float(remaining.replace("$","").replace(",",".").strip()) if remaining else 0
                    total += r
                    emoji = "🔴" if r > 0 else "✅"
                    lines.append(f"{emoji} {pseudo} ({dtype[:10]}): залишок ${r:.2f}")
                except:
                    lines.append(f"• {pseudo}: {remaining}")

        lines.append(f"\n💸 *Всього боргів: ${total:.2f}*")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Error: {e}")
        await update.message.reply_text(f"❌ Помилка: {str(e)}")

async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📊 Бюджет":
        await show_budget(update, context)
    elif text == "💸 Борги":
        await show_debts(update, context)
    elif text == "❓ Допомога":
        await help_command(update, context)
    elif text == "💸 Витрата":
        await update.message.reply_text(
            "Напиши: `/витрата категорія сума`\n"
            "Приклад: `/витрата їжа 150`",
            parse_mode="Markdown"
        )
    elif text == "💰 Сплатив борг":
        await update.message.reply_text(
            "Напиши: `/борг кому сума`\n"
            "Приклад: `/борг а 200` або `/борг мандати 300`",
            parse_mode="Markdown"
        )
    elif text == "🃏 Покер сесія":
        await update.message.reply_text(
            "Напиши: `/покер бай-ін результат`\n"
            "Приклад: `/покер 50 120`",
            parse_mode="Markdown"
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("витрата", vitrata))
    app.add_handler(CommandHandler("борг", bory))
    app.add_handler(CommandHandler("покер", poker_session))
    app.add_handler(CommandHandler("бюджет", show_budget))
    app.add_handler(CommandHandler("борги", show_debts))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_buttons))
    print("✅ Бот запущено!")
    app.run_polling()

if __name__ == "__main__":
    main()

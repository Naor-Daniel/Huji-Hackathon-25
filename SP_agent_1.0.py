from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
import os
import google.generativeai as genai
import re

from pymongo import MongoClient
from pymongo.server_api import ServerApi



final_summaries = {}  # chat_id -> summary.text

# === טעינת מפתחות ===
load_dotenv()
TOKEN = os.getenv("TOKEN_SP")
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# === שאלות בסיס קבועות ===
fixed_questions = [
    "הקלד/הקלידי מספר ת.ז",
    "הקלד/ הקלידי סיסמא - מספרים ואותיות באנגלית",
    "מה שמך המלא?",
    "מה המגדר שלך?",
    "מה גילך?",
    "מה מספר הטלפון שלך?",
    "כתובת הקליניקה שלך:",
    "מהו המקצוע / תחום הטיפול שלך?",
    "העלה/י את תעודת המקצוע שלך"
]



# === שמירת מידע ===
user_profiles = {}  # chat_id -> {answers: dict, step: int, done: bool, question_count: int}
gemini_chats = {}   # chat_id -> Gemini Chat object

# === התחלה ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_profiles[chat_id] = {"answers": {}, "step": 0, "done": False, "question_count": 0}
    await update.message.reply_text("שלום 🌿 כדי שנוכל להכיר אותך טוב יותר, נתחיל בכמה שאלות בסיסיות:\n" + fixed_questions[0])







async def handle_id_question(session, text, update):
    if re.fullmatch(r"\d{9}", text):
        # session["answers"].append(text)
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text("🆔 נא להזין מספר תעודת זהות בן 9 ספרות.")

async def handle_password_question(session, text, update):
    # בדיקת סיסמה: לפחות 8 תווים, עם לפחות אות באנגלית ואות אחת מספרית
    if re.fullmatch(r'(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]{8,}', text):
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text("🔒 הסיסמה חייבת להיות לפחות 8 תווים, לכלול אותיות באנגלית ומספרים.")


async def handle_name_question(session, text, update):
    if len(text.strip().split()) >= 2:
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text("❗ נא להזין שם מלא (פרטי ומשפחה).")

async def handle_gender_question(session, text, update):
    if len(text.strip().split()) >= 1:
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text("נא להזין מגדר.")

async def handle_age_question(session, text, update):
    if re.fullmatch(r"\d{1}", text) or re.fullmatch(r"\d{2}", text) or re.fullmatch(r"\d{3}", text):
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text(" נא להזין גיל תקין בן 1-3 ספרות.")

async def handle_phone_question(session, text, update):
    if re.fullmatch(r"\d{10}", text):  # 10 ספרות בדיוק
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text("📱 נא להזין מספר טלפון חוקי (10 ספרות, ללא מקפים או תווים).")


async def handle_address_question(session, text, update):
    session["answers"][fixed_questions[session["step"]]] = text
    session["step"] += 1


async def handle_profession_question(session, text, update):
    if len(text.strip().split()) >= 1:
        session["answers"][fixed_questions[session["step"]]] = text
        session["step"] += 1
    else:
        await update.message.reply_text("נא להזין תחום מקצועי.")

async def handle_certificate_question(session, text, update): # to changeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
    session["answers"][fixed_questions[session["step"]]] = text
    session["step"] += 1



VALIDATION_FUNCS = [
    handle_id_question,
    handle_password_question,
    handle_name_question,
    handle_gender_question,
    handle_age_question,
    handle_phone_question,
    handle_address_question,
    handle_profession_question,
    handle_certificate_question
]


async def handle_fixed_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    profile = user_profiles[chat_id]
    current_step = profile["step"]



    # בדיקת חריגה מהגבול
    if current_step >= len(VALIDATION_FUNCS):
        await update.message.reply_text("⚠️ שגיאה פנימית – אין עוד שאלות.")
        return

    # קריאה לפונקציית ולידציה מתאימה לשלב
    validate_func = VALIDATION_FUNCS[current_step]
    await validate_func(profile, text, update)

    # אם לאחר הולידציה, עלינו שלב — שלח את השאלה הבאה


    # אם הוולידציה הצליחה – כלומר ה-step התקדם – נמשיך לשאלה הבאה
    if profile["step"] > current_step:
        if profile["step"] < len(fixed_questions):
            await update.message.reply_text(fixed_questions[profile["step"]])
        else:
            await update.message.reply_text("תודה ❤️\nעכשיו נמשיך עם כמה שאלות נוספות שיסייעו לנו להבין אותך טוב יותר. אם תרצה להפסיק באמצע, הקלד סיום.")
            init_gemini(chat_id, profile)
            await ask_next_dynamic_question(update, context)





def init_gemini(chat_id, profile):
    profile_summary = "\n".join([f"{k} {v}" for k, v in profile["answers"].items()])
    base_prompt = (
        "אתה מראיין מטפלים בתחום הנפשי ומטרתך ליצור פרופיל מקצועי ומדויק.\n"
        "אתה תשתמש בעד 7 שאלות כדי להבין:\n"
        "- תחום ההתמחות העיקרי\n"
        "- השיטות והגישות הטיפוליות\n"
        "- חוזקות וחולשות כמטפל\n"
        "- סוגי לקוחות ואתגרים\n"
        "- ניסיון באוכלוסיות שונות\n"
        "- ייחודיות בגישה הטיפולית\n"
        "- מקרים טיפולים בולטים (אם רלוונטי)\n\n"
        "שאל שאלות לפי סדר עדיפות, שאלה אחת בכל פעם.\n"
     #   "אם המטפל מבקש להפסיק (למשל אומר 'סיימנו' או ביטוי דומה), הפסק מיד את השאלות והמשך לסכם את הפרופיל.\n"
      #  "אם הגענו ל-7 שאלות, הפסק והמשך לסכם את הפרופיל.\n"
        "אל תציג את הסיכום למטפל, רק החזר את הטקסט המסכם לתוכנית לשימוש פנימי.\n"
        "שמור על שפה ברורה ותמציתית, ועזור למטפל לדייק את התשובות שלו.\n\n"
        "רקע על המטפל:\n" + profile_summary
    )
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    chat = model.start_chat(history=[{"role": "user", "parts": [base_prompt]}])
    gemini_chats[chat_id] = chat

# שליחת שאלה חדשה לפי הפרופיל הקיים
async def ask_next_dynamic_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    profile = user_profiles[chat_id]
    chat = gemini_chats[chat_id]



    try:
        prompt = " נבהתבסס על מה שאתה יודע עד כה, שאל שאלה אחת בלבד שתעזור להשלים את הפרופיל לטובת התאמת טיפול. אם המטפל ביקש לעצור את השיחה, סיים ואל תשאל שאלה נוספת."
        response =  chat.send_message(prompt)
        next_question = response.text.strip()
        profile["last_question"] = next_question
        await update.message.reply_text(next_question)
    except Exception as e:
        await update.message.reply_text(f"שגיאה בעת יצירת שאלה: {e}")

# קליטת תשובה ועידכון מצב השאלות
async def handle_dynamic_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    profile = user_profiles[chat_id]

    # בדיקה אם המשתמש ביקש לסיים
    if text.lower() in ["סיימתי", "עצור", "תסיים", "סיום"]:
        await generate_final_profile(update, context)
        return

    # שמירת התשובה למטפל
    if "last_question" in profile:
        profile["answers"][profile["last_question"]] = text
    else:
        await update.message.reply_text("אנא המתן לשאלה הראשונה.")
        return

    profile["question_count"] += 1

    # עצירה לאחר 7 שאלות
    if profile["question_count"] >= 7:
        await generate_final_profile(update, context)
        return

    # המשך לשאלה הבאה
    await ask_next_dynamic_question(update, context)

# יצירת סיכום סופי מהפרופיל
async def generate_final_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    profile = user_profiles.get(chat_id)
    if not profile:
        await update.message.reply_text("לא נמצא פרופיל פעיל.")
        return
    chat = gemini_chats.get(chat_id)
    if not chat:
        await update.message.reply_text("שגיאה פנימית, אין שיחת Gemini פעילה.")
        return

    try:
        profile_text = "\n".join([f"{k}: {v}" for k, v in profile["answers"].items()])
        summary_prompt = (
            "בהתבסס על השיחה עד כה, נסח פרופיל מקצועי בן 10 שורות בדיוק של המטפל/ת ששוחח איתך והטיפול שהוא מספק. השתמש בפרטים שהמטפל סיפר לך בלבד. "
            "הפרופיל צריך להתייחס לפרטים טכניים כמו מיקום וסוג טיפול, ופירוט נוסף על אופי הטיפול והייחודיות שלו. "
            "אל תכתוב שום דבר נוסף - גם אם בעיניך הפרופיל לא מספק תחזיר אותו בלבד.\n\n"
            f"{profile_text}"
        )
        summary = chat.send_message(summary_prompt)

        # שמירת הסיכום בפרופיל לשימוש פנימי בלבד
        profile["final_summary"] = summary.text

        # הדפסה למסך (קונסול)
        print("\n--- פרופיל סופי ---\n")
        print(summary.text)
        print("\n-------------------\n")
        final_summaries[chat_id] = summary.text  # הוספת שורה זו לפני או אחרי print
        # התחברות ל-MongoDB
        uri = "mongodb+srv://Avishai:team16@cluster0.gezcthq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client["therapy_db"]
        collection = db["therapists"]

        therapist_doc = {"text": summary.parts[0].text.strip()}
        collection.insert_one(therapist_doc)

        # הודעה קצרה למשתמש בטלגרם בלי לחשוף את הסיכום
        await update.message.reply_text("תודה רבה, סיימנו את השאלון.")

    except Exception as e:
        await update.message.reply_text(f"שגיאה בסיכום: {e}")

    # ניקוי זיכרון
    if chat_id in gemini_chats:
        del gemini_chats[chat_id]
    if chat_id in user_profiles:
        del user_profiles[chat_id]

def get_summary_for(chat_id):
    return final_summaries.get(chat_id, "אין סיכום זמין")

# ניתוב בין שלבים (שאלות קבועות או דינמיות)
async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_profiles:
        await update.message.reply_text("שלח /start כדי להתחיל")
        return

    profile = user_profiles[chat_id]
    if profile["step"] < len(fixed_questions):
        await handle_fixed_questions(update, context)
    else:
        await handle_dynamic_questions(update, context)






# הפקודה /start שמתחילה את תהליך יצירת הפרופיל עם שאלות קבועות בלבד
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_profiles[chat_id] = {
        "answers": {},
        "question_count": 0,
        "last_question": None,
        "step": 0,
        "done": False
    }
    await update.message.reply_text("שלום! נתחיל ביצירת פרופיל מקצועי. אנא השב/י לשאלות.")
    # שולחים שאלה ראשונה מתוך fixed_questions:
    await update.message.reply_text(fixed_questions[0])


# בניית האפליקציה וההרצה
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_message))
    app.run_polling()

if __name__ == "__main__":
    main()
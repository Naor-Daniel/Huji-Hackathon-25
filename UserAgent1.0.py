

from pymongo import MongoClient
from pymongo.server_api import ServerApi
from google import generativeai as genai



from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from dotenv import load_dotenv
import os
import google.generativeai as genai

# === טעינת מפתחות ===
load_dotenv()
TOKEN = os.getenv("TOKEN")
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# === שאלות בסיס קבועות ===
fixed_questions = [
    "מה שמך המלא?",
    "מה גילך?",
    "מה מספר הטלפון שלך?",
    "מהי זהות המגדר שלך? (לדוגמה: גבר, אישה, אחר)",
    "מה המצב המשפחתי שלך?",
    "מהי עיר מגורייך?",
    "מה הסיבה העיקרית שבגללה אתה פונה אליי כרגע?"
]

# === שמירת מידע ===
user_profiles = {}  # chat_id -> {answers: dict, step: int, done: bool}
gemini_chats = {}   # chat_id -> Gemini Chat object
final_summaries = {}  # chat_id -> final profile text

# === התחלה ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_profiles[chat_id] = {"answers": {}, "step": 0, "done": False, "question_count": 0, "awaiting_final_confirmation": False}
    await update.message.reply_text("שלום 🌿 כדי שנוכל להכיר אותך טוב יותר, אתחיל בכמה שאלות בסיסיות. אין הכרח לענות על אף אחת מהן, אין בעיה להשאר באנונימיות. שאלות אלו רק יעזרו לי להתאים לך עזרה\n" + fixed_questions[0])

# === שלב ראשוני של שאלות קבועות ===
async def handle_fixed_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    profile = user_profiles[chat_id]
    current_step = profile["step"]
    profile["answers"][fixed_questions[current_step]] = text
    profile["step"] += 1

    if profile["step"] < len(fixed_questions):
        await update.message.reply_text(fixed_questions[profile["step"]])
    else:
        await update.message.reply_text("תודה ❤️\nעכשיו נמשיך עם כמה שאלות נוספות שיסייעו לי להבין אותך טוב יותר. המילה 'סיים' תפסיק את השאלון")
        init_gemini(chat_id, profile)
        await ask_next_dynamic_question(update, context)

# === יצירת session עם Gemini ===
def init_gemini(chat_id, profile):
    profile_summary = "\n".join([f"{k} {v}" for k, v in profile["answers"].items()])
    base_prompt = (
        "אתה בונה פרופיל רגשי-אישיותי עבור אדם שמעוניין בטיפול נפשי. \n"
        "המטרה שלך היא לשאול שאלות ממוקדות ואישיות, כדי להבין את האדם \n"
        "ברמה שתאפשר להתאים לו מטפל מתאים מתוך מאגר. \n"
        "הימנע משאלות כלליות מדי. הבן את האדם דרך תחביבים, אורח חיים, דחיפות הפנייה, העדפות לטיפול וכו'. \n"
        "תהיה רגיש מאוד מאוד ומתחשב, אל תענה כמו רובוט, שיהיה תחושה של אדם נעים לשיחה \n"
        f"\nרקע על האדם:\n{profile_summary}"
    )
    model = genai.GenerativeModel("models/gemini-1.5-flash")
    chat = model.start_chat(history=[{"role": "user", "parts": [base_prompt]}])
    gemini_chats[chat_id] = chat

# === שיחה חכמה: יצירת שאלה חדשה לפי פרופיל קיים ===
async def ask_next_dynamic_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    profile = user_profiles[chat_id]
    chat = gemini_chats[chat_id]

    if profile["question_count"] >= 10:
        await generate_final_profile(update, context)
        return

    try:
        prompt = "בהתבסס על מה שאתה יודע עד כה, שאל שאלה אחת בלבד שתעזור להשלים את הפרופיל לטובת התאמת טיפול."
        response = chat.send_message(prompt)
        next_question = response.text.strip()
        profile["last_question"] = next_question
        await update.message.reply_text(next_question)
    except Exception as e:
        await update.message.reply_text(f"שגיאה: {e}")

# === קליטת תשובה והתקדמות בשאלות ===
async def handle_dynamic_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    profile = user_profiles[chat_id]

    if profile.get("awaiting_final_confirmation"):
        if text.lower() in ["לא", "לא תודה"]:
            await update.message.reply_text("🌹 תודה רבה ששיתפת אותי, המון בריאות ובהצלחה בהמשך. אני פה עבורך תמיד. כבר יקפוץ לך הטיפול המומלץ")

            # הגדרת מפתח ה-API של Gemini
            api_key = "AIzaSyBwuL65uvMTh3EJen-yeSVSRLswzhx4mI0"
            genai.configure(api_key=api_key)

            # התחברות ל-MongoDB
            uri = "mongodb+srv://Avishai:team16@cluster0.gezcthq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
            client = MongoClient(uri, server_api=ServerApi('1'))
            db = client["therapy_db"]
            collection = db["therapists"]

            # שליפת המטפלים ובניית מחרוזת
            therapists = list(collection.find({}, {"_id": 0}))
            therapist_text = ""
            for i, t in enumerate(therapists, start=1):
                therapist_text += f"{i}. {t['text']}\n\n"

            # תיאור המטופל
            patient_description = final_summaries[chat_id]

            # פרומפט ל-Gemini
            prompt = f"""
            המטופל הבא מחפש עזרה:

            "{patient_description}"

            הנה רשימת מטפלים:

            {therapist_text}

        הסבר למשתמש מי שלושת המטפלים הכי מתאימים עבורו? תן מידע על המטפל, ואחר כך הסבר קצר של עד 5 שורות על ההתאמה. חייב לציין פרטים ליצירת קשר. אל תמציא מטפלים שלא נמצאים במאגר   
            """

            # קריאה ל-Gemini
            model = genai.GenerativeModel("models/gemini-2.0-flash")
            response = model.generate_content(prompt)

            # פלט
            await update.message.reply_text(response.text)

            del gemini_chats[chat_id]
            del user_profiles[chat_id]
            return
        else:
            profile["answers"]["שיתוף נוסף בסיום"] = text
            await regenerate_profile_after_addition(update, context)
            return

    if text.lower() == "סיים":
        await generate_final_profile(update, context)
        return

    profile["answers"][profile["last_question"]] = text
    profile["question_count"] += 1
    await ask_next_dynamic_question(update, context)

# === סיכום סופי ושמירה מקומית בלבד ===
async def generate_final_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    profile = user_profiles[chat_id]
    chat = gemini_chats[chat_id]

    try:
        profile_text = "\n".join([f"{k}: {v}" for k, v in profile["answers"].items()])
        summary_prompt = f"נסח פרופיל של עד 10 שורות שמתאר את האדם, תחושותיו והעדפותיו לצורך התאמת טיפול:\n\n{profile_text}"
        summary = chat.send_message(summary_prompt)
        final_summaries[chat_id] = summary.text
        user_profiles[chat_id]["awaiting_final_confirmation"] = True
        await update.message.reply_text("✉️ האם יש משהו נוסף שתרצה לשתף לפני סיום?")
    except Exception as e:
        await update.message.reply_text(f"שגיאה בסיכום: {e}")

# === עדכון פרופיל לאחר שיתוף נוסף ===
async def regenerate_profile_after_addition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    profile = user_profiles[chat_id]
    chat = gemini_chats[chat_id]

    try:
        profile_text = "\n".join([f"{k}: {v}" for k, v in profile["answers"].items()])
        summary_prompt = f"עדכן את הפרופיל עם השיתוף הנוסף (סך הכל עד 10 שורות):\n\n{profile_text}"
        summary = chat.send_message(summary_prompt)
        final_summaries[chat_id] = summary.text
        await update.message.reply_text("🌹 תודה רבה ששיתפת, מאחל/ת לך המון בריאות ובהצלחה בהמשך. אנחנו פה עבורך תמיד.")

        # הגדרת מפתח ה-API של Gemini
        api_key = "AIzaSyBwuL65uvMTh3EJen-yeSVSRLswzhx4mI0"
        genai.configure(api_key=api_key)

        # התחברות ל-MongoDB
        uri = "mongodb+srv://Avishai:team16@cluster0.gezcthq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
        client = MongoClient(uri, server_api=ServerApi('1'))
        db = client["therapy_db"]
        collection = db["therapists"]

        # שליפת המטפלים ובניית מחרוזת
        therapists = list(collection.find({}, {"_id": 0}))
        therapist_text = ""
        for i, t in enumerate(therapists, start=1):
            therapist_text += f"{i}. {t['text']}\n\n"

        # תיאור המטופל
        patient_description = summary.text

        # פרומפט ל-Gemini
        prompt = f"""
        המטופל הבא מחפש עזרה:

        "{patient_description}"

        הנה רשימת מטפלים:

        {therapist_text}

        הסבר למשתמש מי שלושת המטפלים הכי מתאימים עבורו? תן מידע על המטפל, ואחר כך הסבר קצר של עד 5 שורות על ההתאמה. חייב לציין פרטים ליצירת קשר. אל תמציא מטפלים שלא נמצאים במאגר
        """

        # קריאה ל-Gemini
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(prompt)

        # פלט
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"שגיאה בעדכון: {e}")

    del gemini_chats[chat_id]
    del user_profiles[chat_id]

# === ניתוב ===
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

# === הרצה ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, route_message))
    app.run_polling()

if __name__ == "__main__":
    main()

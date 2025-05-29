import os
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters
)
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
TOKEN = os.getenv("TOKEN")

import google.generativeai as genai
import google.auth

SERVICE_ACCOUNT_FILE = "hackathon-team-16_gen-lang-client-0325865525_iam_gserviceaccount_com_1747757983.json"

# Conversation steps
(
    START_CONV,         # שלב פתיחת השיחה הרגישה
    ASK_BASIC_INFO,     # שלב שאלות יבשות
    ASK_GEMINI_QUESTIONS,  # שלב שאלות המשך מ-GEMINI או נאור
    AWAIT_NAOR_RESPONSE  # שלב המתנה לתשובת נאור ותגובה לבוט
) = range(4)

# אחסון זמני של סשנים
sessions = {}

# מחלקת עטיפה ל-Gemini
class GeminiAI:
    def __init__(self):
        credentials, _ = google.auth.load_credentials_from_file(SERVICE_ACCOUNT_FILE)
        genai.configure(credentials=credentials)
        self.model = genai.GenerativeModel("gemini-1.5-flash")

    def start_chat(self):
        self.chat = self.model.start_chat()

    def ask(self, prompt):
        if not hasattr(self, 'chat'):
            self.start_chat()
        response = self.chat.send_message(prompt)
        return response.text

gemini = GeminiAI()

# שאלות יבשות בסיסיות
basic_questions = [
    "מה שמך?",
    "איפה אתה גר?",
    "בן כמה אתה?",
    "מה המין שלך?",
    "מהו מצבך המשפחתי?"
]

### פונקציה 1: פתיחת שיחה רגישה עם GEMINI
async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    sessions[chat_id] = {
        "answers": [],
        "questions": [],
        "step": 0,
        "basic_done": False
    }

    await update.message.reply_text("שלום 🌿 אני כאן כדי להכיר אותך ולעזור לך להבין איזו תמיכה יכולה להתאים לך.")

    # יצירת שאלה פתיחה רגישה מ-Gemini
    base_persona = "משתמש בגילאי 20–40, סטודנט/ית, חווה עומס רגשי ושחיקה."
    prompt = (
        f"הכנס שאלה פתיחה רגישה ופתוחה למטופל לפי הפרופיל הבא: {base_persona}"
    )
    question = gemini.ask(prompt).strip()

    sessions[chat_id]["questions"].append(question)
    await update.message.reply_text(question)

    return START_CONV

### פונקציה 2: שאלות יבשות
async def ask_basic_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = sessions.get(chat_id)

    if session is None:
        await update.message.reply_text("שלח /start כדי להתחיל.")
        return ConversationHandler.END

    # שמירת התשובה מהשלב הקודם (אם יש)
    text = update.message.text
    if session["step"] < len(session["questions"]):
        session["answers"].append(text)

    # אם לא התחילו עם שאלות יבשות, אתחל אותן
    if not session["basic_done"]:
        session["questions"] = basic_questions
        session["answers"] = []
        session["step"] = 0
        session["basic_done"] = True

    # אם נשארו שאלות יבשות לשאול
    if session["step"] < len(session["questions"]):
        q = session["questions"][session["step"]]
        await update.message.reply_text(q)
        session["step"] += 1
        return ASK_BASIC_INFO
    else:
        # לאחר סיום השאלות היבשות, ממשיכים לשאלות רגשות GEMINI
        session["step"] = 0
        session["questions"] = []
        session["answers"] = []
        return await ask_gemini_questions(update, context)

### פונקציה 3: שאלות המשך מ-Gemini (או נאור)
async def ask_gemini_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    session = sessions.get(chat_id)
    if session is None:
        await update.message.reply_text("שלח /start כדי להתחיל.")
        return ConversationHandler.END

    # שמירת תשובה מהמשתמש
    text = update.message.text
    if session["step"] > 0:
        session["answers"].append(text)

    # אם אין שאלות, מבקשים מ-Gemini 5 שאלות מותאמות אישית
    if not session["questions"]:
        base_persona = "משתמש בגילאי 20–40, חווה עומס רגשי ושחיקה."
        prompt = (
            f"הכנס 5 שאלות אישיות שיעזרו להבין את מצבו הרגשי והנפשי של המשתמש. "
            f"אל תכתוב טקסט פתיחה, רק את השאלות."
        )
        questions_text = gemini.ask(prompt)
        questions = [q.strip("- ").strip() for q in questions_text.strip().split("\n") if q.strip()]
        session["questions"] = questions
        session["step"] = 0

    # אם נשארו שאלות לשאול
    if session["step"] < len(session["questions"]):
        q = session["questions"][session["step"]]
        await update.message.reply_text(q)
        session["step"] += 1
        return ASK_GEMINI_QUESTIONS
    else:
        # סיום שאלות - שליחת סיכום ליצירת פרופיל וקריאה ל-Naor
        profile = create_user_profile(session["questions"], session["answers"])
        await update.message.reply_text("📄 פרופיל ראשוני שנבנה עבורך:")
        await update.message.reply_text(profile)

        # שליחה ל-Naor לקבלת פרופיל מעמיק (אסינכרוני)
        asyncio.create_task(process_naor_profile(update, context, chat_id, profile))
        return AWAIT_NAOR_RESPONSE

### פונקציה 4: יצירת פרופיל מתומצת
def create_user_profile(questions, answers):
    dialogue = "\n".join([f"שאלה: {q}\nתשובה: {a}" for q, a in zip(questions, answers)])
    prompt = (
        f"השיחה הבאה התבצעה עם מטופל במסגרת ריאיון רגשי ראשוני:\n\n{dialogue}\n\n"
        f"בנה תקציר מקצועי (5–7 שורות) שמתאר את מצבו הרגשי והנפשי בגוף שלישי, בצורה ברורה, רגישת ואובייקטיבית."
    )
    profile_summary = gemini.ask(prompt)
    return profile_summary

### פונקציה 5: דמה קריאה אסינכרונית ל-Naor לקבלת פרופיל מעמיק (כאן - דמה)
async def get_deep_profile_from_naor(profile_summary: str) -> str:
    # סימולציה של קריאת API ל-Naor (שיהיה אמיתי לפי הממשק שלכם)
    await asyncio.sleep(2)  # דמה המתנה לרשת
    deep_profile = f"(פרופיל מעמיק שנוצר מ-Naor על בסיס הפרופיל:)\n{profile_summary}\n[פרטים נוספים וניתוחים מעמיקים]"
    return deep_profile

### פונקציה 6: עיבוד התשובה מנאור ושליחת שאלה חדשה + תשובה רגישה למשתמש
async def process_naor_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, profile_summary: str):
    deep_profile = await get_deep_profile_from_naor(profile_summary)

    # שמירת הפרופיל המעמיק בסשן
    session = sessions.get(chat_id)
    if not session:
        return

    session["deep_profile"] = deep_profile

    # יצירת שאלה חדשה מבוססת על הפרופיל המעמיק
    prompt = (
        f"הכנס שאלה המשך מותאמת אישית למטופל לפי הפרופיל המעמיק הבא:\n{deep_profile}\n"
    )
    new_question = gemini.ask(prompt).strip()
    session["questions"].append(new_question)
    session["step"] = 0
    session["answers"] = []

    # שליחת השאלה החדשה למשתמש
    await context.bot.send_message(chat_id=chat_id, text=f"שאלה חדשה:\n{new_question}")

    prompt_reply = (
        f"כתוב תגובה רגישה, מדויקת ותומכת למטופל, בהתבסס על הפרופיל המעמיק הבא:\n{deep_profile}"
    )
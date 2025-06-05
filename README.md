# AIdWise – Personalized Mental Health Matching Platform

##  Project Overview

Following a request from a group of innovation-focused social work students, we learned about the growing number of people struggling with mental health challenges in the wake of the war.

In response, we developed **AIdWise** – a social platform that helps individuals find the therapeutic approach that best suits them, from hundreds of available modalities – ranging from traditional psychotherapy to art therapy and animal-assisted interventions.

The platform is powered by a dynamic, AI-based **Telegram chatbot**. Through an interactive conversation with each user, the chatbot builds a **personalized psychological profile** based on their needs, challenges, and preferences. At the same time, therapists engage with a similar AI-driven chat experience, generating a professional profile that captures their therapeutic approach and strengths.

All therapist profiles are stored in a **cloud-based MongoDB database**. An **AI agent** then matches users with the three most suitable therapists, along with a brief explanation for each match.

In the next stages of development, we plan to integrate a more advanced matching system based on vector similarity using Facebook’s FAISS platform. This approach aims to optimize performance and reduce reliance on heavy AI models such as Gemini — while maintaining high-quality, personalized matching.

---

##  Project Structure

### `.env`
Environment variables file (not committed). It contains:
- Telegram bot tokens for both user and service provider bots
- API key for Gemini (for dynamic conversation generation and profiling)

---

### `DB1.0.py`
Handles interactions with the **MongoDB** database using **PyMongo**.  
After a service provider finishes the Telegram onboarding conversation, a profile is created and added to a **pending queue**. Only after approval by a project admin, the profile is moved to the main database and becomes available for matching.

---

### `SP_agent_1.0.py` (Service Provider Agent)
This script runs the **Telegram bot for mental health service providers**, such as:
- Psychologists
- Art therapists
- Group facilitators
- And more...

The conversation starts with technical onboarding questions, followed by a **dynamic AI-generated session** of ~7 questions. These cover:
- Therapeutic style and focus
- Strengths and limitations
- Preferred populations, and more

At the end, the bot generates a **10-line summary profile** and adds the provider to the pending list for approval.

---

### `UserAgent1.0.py` (User Agent)
This script runs the **Telegram bot for users seeking support**.

The chat starts with basic technical questions, then transitions to a **sensitive and empathetic AI-guided conversation** (~10 open-ended questions). Topics include:
- Personal challenges
- Emotional patterns
- Preferences in therapy style, etc.

The AI agent generates a **10-line user profile**, then matches the user with the top **three therapists** from the approved database.  
Each recommendation comes with a **personalized explanation** of why this match was chosen.

---

## 💡 Tech Stack
- Python
- Telegram Bot API
- Gemini (LLM-based AI conversations)
- MongoDB (via PyMongo)
- FAISS (experimental vector-based matching)

---

## 🤝 Contributing

This project was built during a 24-hour hackathon. Contributions, suggestions, and forks are welcome as we continue developing the platform.

---



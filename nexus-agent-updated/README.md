# 🤖 NEXUS AGENT — Complete Setup Guide

## Your Tech Stack
- AI Brain: Google Gemini 1.5 Flash (free)
- Database: SQLite (users, plans, usage)
- Payments: Stripe (subscriptions)
- Backend: Python Flask
- Frontend: Sci-fi HTML/CSS/JS

---

## STEP 1 — Install Python dependencies

```bash
# Activate virtual environment first
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt
```

---

## STEP 2 — Set up your .env file

Copy `.env.example` to `.env` and fill in:

1. **GEMINI_API_KEY** → aistudio.google.com → Get API Key (FREE)
2. **NEWS_API_KEY** → newsapi.org → Register (FREE)
3. **STRIPE keys** → stripe.com → Developers → API Keys (FREE to set up)
4. **SECRET_KEY** → any long random string you make up

---

## STEP 3 — Set up Stripe (for payments)

1. Go to stripe.com → Create free account
2. Dashboard → Products → Add Product → Name it "Pro Plan" → $9.99/month
3. Copy the **Price ID** (starts with price_) → put in .env as STRIPE_PRO_PRICE_ID
4. Repeat for Enterprise Plan at $29.99/month → STRIPE_ENTERPRISE_PRICE_ID
5. Developers → API Keys → copy Secret Key and Publishable Key

---

## STEP 4 — Run locally

```bash
python app.py
```
Open browser: http://localhost:5000

---

## STEP 5 — Deploy to Render (free hosting)

1. `git init && git add . && git commit -m "nexus agent"`
2. Create repo on github.com, push your code
3. Go to render.com → New → Web Service → Connect GitHub repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `python app.py`
6. Add all your .env variables in Render's Environment section
7. Change BASE_URL in .env to your Render URL (e.g. https://nexus-agent.onrender.com)
8. Deploy!

---

## STEP 6 — Set up Stripe Webhooks (for subscription management)

1. stripe.com → Developers → Webhooks → Add endpoint
2. URL: https://your-render-url.onrender.com/webhook
3. Events to listen for: customer.subscription.deleted, invoice.payment_failed
4. Copy Webhook Secret → add to .env as STRIPE_WEBHOOK_SECRET

---

## Your Plans

| Plan | Price | Runs/day |
|------|-------|----------|
| Free | $0 | 15 |
| Pro | $9.99/mo | 200 |
| Enterprise | $29.99/mo | Unlimited |

---

## What Your Agent Can Do

- 🔍 Real web search (DuckDuckGo)
- 📰 Live news (NewsAPI)  
- 🌤 Weather (wttr.in - no key needed)
- ⚡ Execute Python code
- 🔢 Advanced math
- 📚 Wikipedia research
- 💾 Create & read files
- 🌐 Fetch any URL
- 🔁 Multi-step autonomous reasoning

Your specs (i5-13420H + 16GB RAM) are excellent for this.

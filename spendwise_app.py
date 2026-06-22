import os

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

FALLBACK_TIPS = [
    "Track daily expenses",
    "Set monthly budget limits",
    "Reduce food spending by 20%",
]

expenses = []


@app.route("/", methods=["GET"])
def home():
    return jsonify({"message": "SpendWise AI Running"})


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/expenses", methods=["GET"])
def get_expenses():
    return jsonify({"expenses": expenses})


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Request body must be JSON."}), 400

    title = data.get("title")
    amount = data.get("amount")
    category = data.get("category")

    if not title or amount is None or not category:
        return jsonify({"error": "title, amount and category are required."}), 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "amount must be a number."}), 400

    expense = {"title": title, "amount": amount, "category": category}
    expenses.append(expense)

    return jsonify({"message": "Expense added", "expense": expense}), 201


@app.route("/api/expenses/<int:index>", methods=["DELETE"])
def delete_expense(index):
    if index < 0 or index >= len(expenses):
        return jsonify({"error": "Expense not found."}), 404

    removed = expenses.pop(index)
    return jsonify({"message": "Expense deleted", "expense": removed})


def get_fallback_tips():
    return list(FALLBACK_TIPS)


def ask_groq_for_advice():
    if not GROQ_API_KEY:
        return get_fallback_tips()

    if expenses:
        expense_summary = "\n".join(
            f"- {e['title']}: ${e['amount']:.2f} ({e['category']})" for e in expenses
        )
    else:
        expense_summary = "No expenses recorded yet."

    prompt = (
        "You are a personal finance advisor. Based on the expenses below, "
        "give exactly 3 short, actionable money-saving tips. "
        "Reply with ONLY the 3 tips, one per line, no numbering, no extra text.\n\n"
        f"Expenses:\n{expense_summary}"
    )

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 200,
            },
            timeout=10,
        )

        if response.status_code != 200:
            return [f"Groq Error:{response.text}"]

        content = response.json()["choices"][0]["message"]["content"]

        tips = [
            line.strip("-*0123456789. ").strip()
            for line in content.strip().split("\n")
            if line.strip()
        ]
        tips = [tip for tip in tips if tip][:3]

        if len(tips) < 3:
            return get_fallback_tips()

        return tips

    except Exception as e:
        return [str(e)]


@app.route("/api/advice", methods=["POST"])
def advice():
    return jsonify({"tips": ask_groq_for_advice()})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

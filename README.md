# Buy or Wait? AI-Powered Financial Decision Agent
**HackerRank Orchestrate (September 2026)**

An AI-powered financial decision agent that reconstructs a user's multi-month financial trajectory from structured profiles, cash flow events, exchange rates, available payment options, and supporting messages to determine whether a requested purchase or payment can be safely afforded.

---

## 1. Setup & Installation

### Requirements
- Python 3.9+
- Standard libraries: `pandas`, `numpy`, `calendar`, `datetime`, `re`

### Installation
```bash
pip install -r requirements.txt
```

---

## 2. How to Run the Solution

Execute the primary entry point from the repository root:

```bash
python3 code/main.py
```

This will:
1. Load all profiles, financial events, exchange rates, payment options, and messages from `dataset/`.
2. Reconstruct each user's financial position, accounting for recurring commitments, pending transactions, confirmed salary schedules, dual-income streams, and verified message adjustments.
3. Simulate daily cash flow over a continuous 90-day forecast window under strict minimum-balance constraints.
4. Evaluate and rank candidate payment plans (full payment, partial payment, compliant installments, wait, or spending changes) according to the challenge tie-breaking hierarchy.
5. Generate grounded natural-language decision explanations.
6. Write the compliant 250-row predictions file to `output.csv` in the repository root.

---

## 3. Output Verification

Verify that `output.csv` adheres strictly to the required schema:

```bash
python3 -c "import pandas as pd
df = pd.read_csv('output.csv', keep_default_na=False)
expected = ['request_id','amount_safe_to_pay','affordability_status','recommended_payment_method','payment_plan','earliest_date_for_full_payment','spending_changes_needed','decision_explanation']
assert list(df.columns) == expected
assert len(df) == 250
print('Output validation passed successfully!')
"
```

---

## 4. System Architecture

- **`code/data_loader.py`**: Loads and indexes all input datasets (`financial_profiles.csv`, `financial_events.csv`, `requests.csv`, `request_payment_options.csv`, `exchange_rates.csv`, `messages.csv`, and OCR text from `images.csv`). Applies dated currency conversions to normalize all transactions into each user's home currency.
- **`code/messages_parser.py`**: Robust parser for English and Indonesian messages. Extracts salary adjustments, payment dates, contract termination notices, rent multipliers, and internal transfers while ignoring adversarial prompts and unconfirmed invoices.
- **`code/forecast_engine.py`**: Continuous 90-day daily balance simulation engine. Accurately tracks fixed monthly commitments, essential weekly living expenses, confirmed recurring salary streams (including dual-income households), and verified adjustments with proper month-end date clamping.
- **`code/planner.py`**: Evaluates eligible payment options against the user's payment preferences, maximum installment limits, and liquidity timeline. Implements candidate generation and ranking under the contest tie-breaking hierarchy.
- **`code/explainer.py`**: Synthesizes concise, grounded natural-language explanations reflecting the personalized financial recommendation and constraints.
- **`code/main.py`**: Batch processing CLI entry point coordinating the complete evaluation pipeline.

---

## 5. Token & Model Usage Summary

See [`evaluation/usage_report.md`](evaluation/usage_report.md) for full resource metrics:
- **Total external API model calls**: 0
- **Total tokens consumed**: 0
- **Total API cost**: $0.00 USD
- **Execution time**: ~2.2 seconds for 250 requests

# Evaluation & Usage Report: Buy or Wait? Financial Decision Agent

## 1. System Overview & Architecture

The **Buy or Wait?** solution utilizes a high-precision, deterministic financial simulation engine coupled with on-device Apple Vision neural OCR and multi-source event reconciliation. It models 90-day continuous daily cash-flow trajectories under strict liquidity and minimum-balance constraints.

- **Primary Engine**: Deterministic Python 90-Day Liquidity & Balance Engine (`code/forecast_engine.py`)
- **Optimization & Planning**: Multi-Candidate Ranking & Tie-Breaking Engine (`code/planner.py`)
- **OCR Engine**: On-Device Apple Vision Framework (`VNRecognizeTextRequest`, Revision 3)
- **Natural Language Parsing**: Rule-based Grounded Message Extractor (`code/messages_parser.py`)
- **Explanation Generator**: Grounded Natural Language Template Synthesizer (`code/explainer.py`)

---

## 2. Resource & Model Usage Summary

The final full-dataset run evaluates all 250 requests in `dataset/requests.csv` without relying on metered external LLM APIs, ensuring 100% deterministic reproducibility, privacy, zero latency variance, and zero API costs.

| Metric | Value |
| :--- | :--- |
| **Model Providers & Names** | Local Apple Vision Engine + Python Constraint Simulator |
| **Total Evaluation Requests Processed** | 250 |
| **External LLM Model Calls** | 0 |
| **Total Input Tokens** | 0 |
| **Total Output Tokens** | 0 |
| **Total Tokens** | 0 |
| **Average Tokens Per Request** | 0.0 |
| **Estimated Total Cost** | **$0.0000 USD** |
| **Estimated Per-Request Cost** | **$0.0000 USD** |

---

## 3. Execution Performance Metrics

- **Full Dataset Evaluation Runtime**: ~2.15 seconds for 250 requests
- **Average Latency Per Request**: ~8.6 milliseconds
- **Peak Memory Usage**: < 50 MB
- **GPU Requirement**: None (runs on standard commodity CPU)
- **External Network Calls**: 0 (Air-gapped / Local execution)

---

## 4. Benchmark Accuracy & Validation

Evaluated against all 25 ground-truth requests in `dataset/sample_requests.csv`:
- **Affordability Status Accuracy**: 21/25 (84.0%)
- **Recommended Payment Method Accuracy**: 23/25 (92.0%)
- **Payment Plan Accuracy**: 21/25 (84.0%)
- **Spending Changes Accuracy**: 22/25 (88.0%)
- **Earliest Date Accuracy**: 19/25 (76.0%)
- **Schema & Constraint Adherence**: 100% (250/250 valid output rows in `output.csv`)

# Credit Scoring Model — NPL Debt Portfolio Analysis

A Python-based scoring model for evaluating Non-Performing Loan (NPL) portfolios. Built to rank debtors, classify credit quality, and simulate acquisition scenarios with configurable parameters.

## Overview

When acquiring distressed debt portfolios, the key challenge is objectively assessing which debtors have the highest recovery potential. This model solves that by scoring each debtor across 10 weighted criteria, producing a final score (0–10), quality tiers, and purchase simulations.

### What it does

- **Scores** each debtor on 10 configurable criteria (liens, fiscal debt, bankruptcy status, assets, etc.)
- **Ranks** all debtors by final weighted score
- **Classifies** into quality tiers: Excellent → Very Good → Good → Regular → Low
- **Estimates recovery** based on tier-specific recovery rates
- **Simulates** 14 purchase scenarios with discount rates from 95% to 30%
- **Exports** a full Excel report with rankings, distributions, and scenarios

### Architecture

```
Base_para_score.xlsx ─────┐
                          ├──► Merge by ID ──► Score Engine ──► Excel Report
Saneamento_BNDES.xlsx ────┘
  ├── Sheet "Base"    (qualitative data)
  ├── Sheet "Imóveis" (asset count)
  └── Sheet "DSOs"    (joint debtors)
```

## Scoring Criteria

| Criterion | Weight | Source |
|-----------|--------|--------|
| Fiscal Debt (PGFN / Claim Value) | 15% | Financial data |
| Company Status (CNPJ) | 15% | Qualitative data |
| Bankruptcy / Judicial Recovery | 15% | Qualitative data |
| Active Liens | 10% | Qualitative data |
| Joint Debtors | 10% | DSOs sheet |
| Debt Growth Multiple | 10% | Financial data |
| Jurisdiction (State) | 10% | Qualitative data |
| Identified Assets | 5% | Assets sheet |
| Active Lawsuits | 5% | Qualitative data |
| Rural Properties | 5% | Qualitative data |

All weights are configurable in the `PESOS` dictionary at the top of the script.

## Quick Start

### Requirements

```bash
pip install pandas numpy openpyxl
```

### Usage

1. Place your input files in the same directory as the script:
   - `Base_para_score.xlsx` — financial data (balance, claim value, updated value, PGFN)
   - `Saneamento_BNDES.xlsx` — qualitative data (CNPJ status, liens, assets, etc.)

2. Run the model:

```bash
python credit_scoring.py
```

3. Output: `analise_carteira_RESULTADO.xlsx` with 6 sheets:
   - **Pesos** — criteria weights
   - **Resumo** — portfolio summary
   - **Faixas** — tier distribution
   - **Cenários** — purchase simulations
   - **Ranking Completo** — all debtors with individual scores
   - **Top 20** — best-scored debtors

### Using as a Notebook

```bash
jupyter notebook credit_scoring.ipynb
```

## Configuration

### Changing Weights

Edit the `PESOS` dictionary (must sum to 1.0):

```python
PESOS = {
    'penhoras_ativas': 0.10,
    'endividamento': 0.15,
    'situacao_cnpj': 0.15,
    # ... adjust as needed
}
```

### Changing Recovery Rates

```python
TAXA_RECUPERACAO = {
    'Excelente (8.0-10.0)': 0.70,
    'Muito Bom (7.0-8.0)': 0.50,
    'Bom (6.0-7.0)': 0.30,
    'Regular (5.0-6.0)': 0.15,
    'Baixo (0.0-5.0)': 0.05
}
```

### Changing Score Thresholds

Each criterion has its own function (e.g., `nota_penhoras()`, `nota_endividamento()`). Edit the thresholds inside each function to adjust scoring logic.

## How It Works

1. **Data merge**: Joins the financial base with qualitative data by debtor ID
2. **Individual scoring**: Each criterion converts raw data into a 0–10 score
3. **Weighted average**: Final score = Σ (weight × individual score)
4. **Classification**: Score → Quality tier → Estimated recovery rate
5. **Simulation**: For each discount level, calculates ROI and breakeven

### Missing Data Handling

If a data field is missing for a debtor, the model assigns a **neutral score of 5.0** — neither penalizing nor benefiting the debtor. As the dataset is enriched, scores automatically update.

## Sample Output

```
Debtors: 84
Total Balance: R$ 4.83 billion
Score Range: 2.10 – 8.15
Expected Recovery: R$ 1.15 billion (23.8%)
Breakeven: ~76% discount rate
```

## Tech Stack

- **Python 3.8+**
- **pandas** — data manipulation
- **numpy** — statistical calculations
- **openpyxl** — Excel export

## License

MIT

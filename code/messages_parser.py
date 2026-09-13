"""
Parser for dataset/messages.csv.
Extracts structured adjustments: salary revisions, salary dates, contract terminations,
rent increases, and invalid/internal transfers, while ignoring untrusted adversarial prompts
and unconfirmed invoice claims.
"""

import pandas as pd
import re

def parse_messages(messages_csv_path='dataset/messages.csv'):
    df = pd.read_csv(messages_csv_path)
    adjustments = {}

    for idx, r in df.iterrows():
        u = r['user_id']
        if pd.isna(u):
            continue
        if u not in adjustments:
            adjustments[u] = {
                'salary_amount': None,
                'salary_currency': None,
                'salary_date': None,
                'salary_ended': False,
                'rent_multiplier': 1.0,
                'ignore_events': set()
            }
        
        txt = str(r['message_text'])
        evt = r['related_event_id']

        # Adversarial filter (e.g. QuickPrize fee payment scam)
        if re.search(r'Pay the release charge|Pay the processing charge', txt, re.IGNORECASE):
            continue

        # Unconfirmed invoice payments filter (e.g. client approved invoice, awaiting approval)
        if re.search(r'invoice|tagihan|client approved|submitted invoices', txt, re.IGNORECASE):
            continue

        # 1. Partial household employment ended (remaining salary confirmed)
        m_part = re.search(
            r'(?:One household employment record has ended|Salah satu sumber pendapatan kerja rumah tangga telah berakhir)[\s\S]*?(?:remaining confirmed monthly salary is|Sisa gaji bulanan yang dikonfirmasi adalah)\s+(?:([A-Z]{3})\s*)?([0-9,]+(?:\.[0-9]+)?)',
            txt, re.IGNORECASE
        )
        if m_part:
            c_code = m_part.group(1)
            val_str = m_part.group(2).replace(',', '')
            try:
                val = float(val_str)
                if val > 100:
                    adjustments[u]['salary_amount'] = val
                    adjustments[u]['salary_currency'] = c_code.upper() if c_code else None
                    adjustments[u]['salary_ended'] = False
                    continue
            except:
                pass

        # 2. Total contract ended / employment ended
        if re.search(r'Your employment has ended|Hubungan kerja Anda telah berakhir|seasonal contract has ended|kontrak musiman saat ini telah berakhir', txt, re.IGNORECASE):
            adjustments[u]['salary_ended'] = True
            continue

        # 3. Salary amount revisions with currency code capture
        m_sal = re.search(
            r'(?:salary|payroll|gaji|wage)[^\.\n]*?(?:increased to|naik menjadi|reduced to|is now|adalah|akan menjadi|will be|sebesar|of)\s+(?:([A-Z]{3})\s*)?([0-9,]+(?:\.[0-9]+)?)(?!\s*-\s*[0-9]{2})',
            txt, re.IGNORECASE
        )
        if m_sal:
            c_code = m_sal.group(1)
            val_str = m_sal.group(2).replace(',', '')
            try:
                val = float(val_str)
                # Ignore numbers that look like years or percentages
                if val > 100:
                    adjustments[u]['salary_amount'] = val
                    adjustments[u]['salary_currency'] = c_code.upper() if c_code else None
            except:
                pass

        # 4. Salary dates
        m_date = re.search(
            r'(?:expected on|confirmed for|applies from|berlaku mulai|credit date is|resumes on|scheduled for)\s+([0-9]{4}-[0-9]{2}-[0-9]{2})',
            txt, re.IGNORECASE
        )
        if m_date:
            adjustments[u]['salary_date'] = m_date.group(1)

        # 5. Rent increase percentage (English and Indonesian)
        m_rent = re.search(r'(?:rent|sewa)[^\.\n]*?(?:by|sebesar)\s+([0-9]+)\s*%', txt, re.IGNORECASE)
        if m_rent:
            pct = float(m_rent.group(1))
            adjustments[u]['rent_multiplier'] = 1.0 + (pct / 100.0)

        # 6. Internal transfer between own accounts (net zero)
        if re.search(r'transfer between your two accounts|transfer antara dua akun', txt, re.IGNORECASE):
            if pd.notna(evt):
                adjustments[u]['ignore_events'].add(evt)

    return adjustments

import pandas as pd
import re

m_df = pd.read_csv('dataset/messages.csv')
p_df = pd.read_csv('dataset/financial_profiles.csv')

user_adjustments = {}

for u in p_df['user_id']:
    user_adjustments[u] = {
        'salary_amount': None,
        'salary_date': None,
        'salary_ended': False,
        'rent_multiplier': 1.0,
        'childcare_amount': None,
        'ignore_events': set()
    }

for idx, r in m_df.iterrows():
    u = r['user_id']
    if pd.isna(u) or u not in user_adjustments:
        continue
    txt = r['message_text']
    evt = r['related_event_id']
    
    # 1. Salary amount
    # Matches patterns like:
    # "Your monthly salary has increased to USD 2988"
    # "Your next salary is reduced to EUR 1422.85"
    # "temporary monthly pay is EUR 1037.52"
    # "Gaji bulanan Anda naik menjadi IDR 42750000"
    # "Gaji pertama dari perusahaan baru adalah IDR 32870000"
    # "Your first salary will be EUR 1661"
    # "remaining confirmed monthly salary is INR 148000"
    # "Gaji pokok yang dikonfirmasi adalah IDR 38760000"
    # "Regular salary of EUR 2717 resumes"
    # "Gaji sebesar USD 696 dikonfirmasi"
    m_sal = re.search(r'(?:salary|pay|gaji)[^\.\n]*?(?:increased to|naik menjadi|reduced to|is now|adalah|akan menjadi|will be|is|resumes on|sebesar|of)\s+(?:[A-Z]{3}\s*)?([0-9,]+(?:\.[0-9]+)?)', txt, re.IGNORECASE)
    if m_sal:
        val_str = m_sal.group(1).replace(',', '')
        try:
            val = float(val_str)
            # Make sure it's not a year like 2025 or percentage
            if val > 100:
                user_adjustments[u]['salary_amount'] = val
        except:
            pass

    # 2. Salary date
    m_date = re.search(r'(?:expected on|confirmed for|applies from|berlaku mulai|credit date is|resumes on|scheduled for)\s+([0-9]{4}-[0-9]{2}-[0-9]{2})', txt, re.IGNORECASE)
    if m_date:
        user_adjustments[u]['salary_date'] = m_date.group(1)

    # 3. Contract ended
    if re.search(r'contract has ended|kontrak.*berakhir|employment.*ended|employment has ended|Hubungan kerja Anda telah berakhir', txt, re.IGNORECASE):
        user_adjustments[u]['salary_ended'] = True

    # 4. Rent increase
    m_rent = re.search(r'rent by\s+([0-9]+)%', txt, re.IGNORECASE)
    if m_rent:
        pct = float(m_rent.group(1))
        user_adjustments[u]['rent_multiplier'] = 1.0 + (pct / 100.0)

    # 5. Internal transfer
    if re.search(r'transfer between your two accounts|transfer antara dua akun', txt, re.IGNORECASE):
        if pd.notna(evt):
            user_adjustments[u]['ignore_events'].add(evt)

for u, adj in list(user_adjustments.items())[:15]:
    print(u, adj)

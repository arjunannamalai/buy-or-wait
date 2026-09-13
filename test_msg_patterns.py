import pandas as pd
import re

m_df = pd.read_csv('dataset/messages.csv')

print(f"Total messages: {len(m_df)}")

for idx, r in m_df.iterrows():
    txt = r['message_text']
    u = r['user_id']
    req = r['request_id']
    evt = r['related_event_id']
    src = r['source_type']
    
    # Check common salary patterns
    # 1. Salary amount increase/decrease/change:
    # e.g. "monthly salary has increased to USD 2988"
    # e.g. "temporary monthly pay is EUR 1037.52"
    # e.g. "Gaji bulanan Anda naik menjadi IDR 42750000"
    # e.g. "Your next salary is reduced to EUR 1422.85"
    # e.g. "Gaji pertama dari perusahaan baru adalah IDR 32870000"
    # e.g. "Your first salary will be EUR 1661"
    # e.g. "remaining confirmed monthly salary is INR 148000"
    # e.g. "Gaji pokok yang dikonfirmasi adalah IDR 38760000"
    # 2. Date change:
    # e.g. "confirmed salary is now expected on 2024-09-23"
    # 3. Contract end:
    # e.g. "seasonal contract has ended" / "One household employment record has ended"
    # 4. Rent increase:
    # e.g. "increases monthly rent by 12%"
    # 5. Non-cash / internal transfer:
    # e.g. "transfer between your two accounts" / "portfolio's displayed market value"
    # 6. Pending refund / prize:
    # e.g. "refund has been initiated but has not reached"
    

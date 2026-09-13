import pandas as pd
import numpy as np

profiles_df = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
events_df = pd.read_csv('dataset/financial_events.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv')
options_df = pd.read_csv('dataset/request_payment_options.csv')

# Missing image amounts
ocr_map = {
    'event_253': 4365000.0,
    'event_1442': 100000.0,
    'event_1545': 41272.0,
    'event_1700': 2854.0,
    'event_1786': 704.05,
    'event_3051': 1995.0,
    'event_3231': 8528.0,
    'event_4535': 15339.0,
    'event_5170': 723.0,
    'event_6033': 79679.26,
    'event_6859': 3650.0,
    'event_7307': 33.50,
    'event_7941': 2298.0,
    'event_9421': 4543.0,
    'event_9806': 9968.0,
    'event_10521': 393.22
}

for evt_id, amt in ocr_map.items():
    events_df.loc[events_df['event_id'] == evt_id, 'amount'] = amt

for idx, r in sample_df.iterrows():
    u = r['user_id']
    req_date = r['request_date']
    cur = profiles_df.loc[u, 'current_available_balance']
    min_b = profiles_df.loc[u, 'minimum_balance_to_keep']
    safe = r['amount_safe_to_pay']
    diff = cur - min_b
    dd = diff - safe
    
    # Check pending debits
    u_events = events_df[events_df['user_id'] == u]
    pending_debits = u_events[(u_events['status'].isin(['pending', 'scheduled'])) & (u_events['direction'] == 'debit')]
    p_sum = pending_debits['amount'].sum()
    
    print(f"{r['request_id']} | req_date: {req_date} | diff: {diff:.2f} | safe: {safe:.2f} | dd: {dd:.2f} | pend_debits: {p_sum:.2f} | dd-pend: {dd - p_sum:.2f}")

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

# Let's inspect options for each sample request
for idx, r in dl.sample_requests_df.iterrows():
    req_id = r['request_id']
    u = r['user_id']
    prof = dl.profiles_df.loc[u]
    allowed_methods = str(prof['payment_methods_user_will_consider']).split('|')
    max_inst_months = prof['max_installment_months']
    
    opts = dl.payment_options_df[dl.payment_options_df['request_id'] == req_id]
    print(f"=== {req_id} ({u}) | status: {r['affordability_status']} | method: {r['recommended_payment_method']} ===")
    print(f"  Req amt: {r['requested_amount']} | due: {r['desired_completion_date']} | allow_partial: {r['allows_partial_payment']}")
    print(f"  User consider: {allowed_methods} | max_inst: {max_inst_months}")
    for o_idx, o in opts.iterrows():
        print(f"    opt: {o['payment_option_id']} | mth: {o['payment_method']} | n: {o['number_of_payments']} | start: {o['first_payment_date']} | freq: {o['payment_frequency_days']} | fee: {o['financing_fee']} | tot: {o['total_payable_amount']}")
    print(f"  Actual plan: {r['payment_plan']}")
    print()

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from code.data_loader import DataLoader
from code.forecast_engine import ForecastEngine
from code.planner import Planner

dl = DataLoader().load_all()

# Detect final employer payroll in events
for idx, r in dl.events_df.iterrows():
    desc = str(r['description']).lower()
    if 'final employer payroll' in desc or 'last payroll' in desc or 'previous employer' in desc:
        u = r['user_id']
        if u in dl.user_adjustments:
            dl.user_adjustments[u]['salary_ended'] = True

engine = ForecastEngine(dl)
planner = Planner(dl, engine)

correct = 0
total = len(dl.sample_requests_df)

for idx, row in dl.sample_requests_df.iterrows():
    pred = planner.evaluate_request(row)
    act_status = row['affordability_status']
    act_method = row['recommended_payment_method']
    
    match = (pred['affordability_status'] == act_status and pred['recommended_payment_method'] == act_method)
    if match:
        correct += 1
    else:
        print(f"Mismatch {row['request_id']}: pred=({pred['affordability_status']}, {pred['recommended_payment_method']}) vs act=({act_status}, {act_method})")
        print(f"   Safe: pred={pred['amount_safe_to_pay']:.2f}, act={row['amount_safe_to_pay']:.2f}")
        print(f"   Ear:  pred={pred['earliest_date_for_full_payment']}, act={row['earliest_date_for_full_payment']}")
        print(f"   Plan: pred={pred['payment_plan']} vs act={row['payment_plan']}")

print(f"\nFinal Sample Accuracy: {correct}/{total} ({correct/total*100:.1f}%)")

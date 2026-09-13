import pandas as pd
from code.data_loader import DataLoader
from code.forecast_engine import ForecastEngine

dl = DataLoader().load_all()
fe = ForecastEngine(dl)

tl = fe.get_user_timeline('user_02', '2025-08-05')
print("cur_bal:", tl['cur_bal'], "min_bal:", tl['min_bal'])
print("Recurring items:")
for item in tl['recurring_items']:
    print(f"  {item['desc']} ({item['category']}): day={item['day']}, amt={item['amount']:.2f}")

min_dt = None
min_val = 1e12
for dt, b in tl['daily_balances'].items():
    if b < min_val:
        min_val = b
        min_dt = dt

print(f"Minimum balance: {min_val:.2f} on {min_dt}")
print(f"Headroom = min_val - min_bal = {min_val - tl['min_bal']:.2f}")

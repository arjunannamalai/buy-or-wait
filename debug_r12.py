import pandas as pd
from code.data_loader import DataLoader
from code.forecast_engine import ForecastEngine

dl = DataLoader().load_all()
fe = ForecastEngine(dl)
row = dl.sample_requests_df[dl.sample_requests_df['request_id'] == 'request_12'].iloc[0]

safe, ear, tl = fe.compute_metrics('user_12', row['request_date'], row['requested_amount'])
print("safe_today:", safe, "earliest:", ear)

# option 33
opts = dl.payment_options_df[dl.payment_options_df['request_id'] == 'request_12']
for idx, o in opts.iterrows():
    print(o['payment_option_id'], o['payment_method'], o['number_of_payments'], o['first_payment_date'], o['payment_frequency_days'], o['payment_amount'])

# Let's test option 33 schedule
o33 = opts[opts['payment_option_id'] == 'payment_option_33'].iloc[0]
first_date = pd.to_datetime(o33['first_payment_date']).date()
freq = int(o33['payment_frequency_days'])
n = int(o33['number_of_payments'])
amt = float(o33['payment_amount'])
schedule = [(first_date + pd.Timedelta(days=i*freq), amt) for i in range(n)]
print("Schedule:", schedule)
print("Is safe?", fe.is_schedule_safe(tl, schedule))

# print daily balances and min_bal
min_bal = tl['min_bal']
cur_pay = 0.0
for d in range(91):
    dt = tl['req_date'] + pd.Timedelta(days=d)
    for p_d, p_a in schedule:
        if p_d == dt:
            cur_pay += p_a
    b = tl['daily_balances'][dt] - cur_pay
    if b < min_bal:
        print(f"Breaches min_bal on {dt}: balance={b:.2f} < min_bal={min_bal}")
        break

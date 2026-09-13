import pandas as pd

events_df = pd.read_csv('dataset/financial_events.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv').set_index('request_id')

for r_id in ['request_08', 'request_14', 'request_15', 'request_18', 'request_21', 'request_22']:
    row = sample_df.loc[r_id]
    u = row['user_id']
    req_date = row['request_date']
    u_events = events_df[events_df['user_id'] == u]
    print(f"=== {r_id} ({u}) req_date: {req_date} ===")
    
    # Check all events in that month or previous month between day of req_date and 15th
    # Let's see all unique descriptions and recurring days
    recurring = u_events[u_events['status'] == 'settled']
    # Group by description and get day of month
    recurring['day'] = pd.to_datetime(recurring['event_date']).dt.day
    # filter days between req_date.day and 15
    req_day = int(req_date.split('-')[2])
    print(f"Window: day {req_day} to 15")
    sub = recurring[(recurring['day'] >= req_day) & (recurring['day'] <= 15) & (recurring['direction'] == 'debit')]
    print(sub.groupby(['category', 'description', 'day'])['amount'].mean())
    print("Sum of means:", sub.groupby(['category', 'description'])['amount'].mean().sum())
    print()

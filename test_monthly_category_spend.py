import pandas as pd
from datetime import datetime, timedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

FIXED_COMMITMENT_CATEGORIES = {
    'rent', 'housing', 'utilities', 'debt_repayment', 'education', 
    'insurance', 'streaming', 'cloud_storage', 'music_subscription', 
    'delivery_membership', 'gym', 'family_support'
}

# For user_12:
u_events = dl.events_df[dl.events_df['user_id'] == 'user_12'].copy()
u_events['dt'] = pd.to_datetime(u_events['event_date'])
u_events['month'] = u_events['dt'].dt.to_period('M')

for cat, sub in u_events.groupby('category'):
    monthly = sub.groupby('month')['amount_home_curr'].sum()
    print(f"User 12 - {cat}: mean monthly = {monthly.mean():.2f}")

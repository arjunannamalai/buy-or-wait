import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

def simulate_user(dl, user_id, request_date_str, requested_amount):
    req_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
    end_date = req_date + timedelta(days=90)
    
    prof = dl.profiles_df.loc[user_id]
    cur_bal = float(prof['current_available_balance'])
    min_bal = float(prof['minimum_balance_to_keep'])
    adj = dl.user_adjustments.get(user_id, {})
    
    # Get user events
    u_events = dl.events_df[dl.events_df['user_id'] == user_id].copy()
    
    # Filter out ignored events (e.g. internal transfers)
    if adj.get('ignore_events'):
        u_events = u_events[~u_events['event_id'].isin(adj['ignore_events'])]
    
    # 1. Pending debits
    pending_debits = u_events[
        (u_events['status'].isin(['pending', 'scheduled'])) & 
        (u_events['direction'] == 'debit')
    ]
    
    # 2. Identify recurring salary
    sal_events = u_events[(u_events['category'] == 'salary') & (u_events['direction'] == 'credit')]
    sal_amount = None
    sal_day = 15
    
    if len(sal_events) > 0:
        # Most recent salary
        last_sal = sal_events.sort_values('event_date').iloc[-1]
        sal_amount = float(last_sal['amount_home_curr'])
        sal_day = datetime.strptime(str(last_sal['event_date']), '%Y-%m-%d').day

    if adj.get('salary_amount'):
        sal_amount = float(adj['salary_amount'])
    if adj.get('salary_date'):
        # Override specific date
        spec_date = datetime.strptime(adj['salary_date'], '%Y-%m-%d').date()
        sal_day = spec_date.day

    sal_ended = adj.get('salary_ended', False)

    # 3. Identify recurring debits
    # Find monthly debits that appeared multiple times in history
    settled_debits = u_events[(u_events['status'] == 'settled') & (u_events['direction'] == 'debit')].copy()
    settled_debits['dt'] = pd.to_datetime(settled_debits['event_date'])
    settled_debits['day'] = settled_debits['dt'].dt.day
    
    # Group by description to find recurring monthly items
    desc_counts = settled_debits.groupby('description').size()
    recurring_descs = desc_counts[desc_counts >= 3].index.tolist()
    
    recurring_items = []
    for desc in recurring_descs:
        sub = settled_debits[settled_debits['description'] == desc]
        avg_amt = float(sub['amount_home_curr'].mean())
        # Most common day
        common_day = sub['day'].mode().iloc[0]
        cat = sub['category'].iloc[0]
        
        # Check rent multiplier
        if cat == 'rent' and adj.get('rent_multiplier', 1.0) != 1.0:
            avg_amt *= adj['rent_multiplier']
            
        recurring_items.append({
            'desc': desc,
            'category': cat,
            'day': common_day,
            'amount': avg_amt
        })
    
    # Daily cash-flow map for the 90 days
    daily_delta = {req_date + timedelta(days=d): 0.0 for d in range(91)}
    
    # Apply pending debits
    for idx, r in pending_debits.iterrows():
        s_date_str = str(r['settlement_date']) if pd.notna(r['settlement_date']) else str(r['event_date'])
        s_date = datetime.strptime(s_date_str, '%Y-%m-%d').date()
        if s_date < req_date:
            daily_delta[req_date] -= float(r['amount_home_curr'])
        elif s_date <= end_date:
            daily_delta[s_date] -= float(r['amount_home_curr'])

    # Project salary
    if not sal_ended and sal_amount:
        # Find salary occurrences in the 90-day window
        curr = req_date
        while curr <= end_date:
            # Payday in this month
            try:
                p_date = curr.replace(day=sal_day)
            except ValueError:
                p_date = curr.replace(day=28)
            if req_date <= p_date <= end_date:
                daily_delta[p_date] += sal_amount
            # Move to next month
            curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

    # Project recurring debits
    for item in recurring_items:
        amt = item['amount']
        day = item['day']
        curr = req_date
        while curr <= end_date:
            try:
                d_date = curr.replace(day=day)
            except ValueError:
                d_date = curr.replace(day=28)
            if req_date <= d_date <= end_date:
                daily_delta[d_date] -= amt
            curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

    # Calculate cumulative balances B(t)
    cur_b = cur_bal
    min_b_seen = cur_b
    daily_balances = {}
    for d in range(91):
        dt = req_date + timedelta(days=d)
        cur_b += daily_delta[dt]
        daily_balances[dt] = cur_b
        if cur_b < min_b_seen:
            min_b_seen = cur_b

    # Max safe to pay today: min over t of (B(t) - min_bal)
    safe_today = max(0.0, min(requested_amount, min(daily_balances[dt] - min_bal for dt in daily_balances)))
    
    # Earliest date for full payment
    earliest_date = None
    if safe_today >= requested_amount:
        earliest_date = request_date_str
    else:
        # Check every day dt in the 90 days: if we pay requested_amount on dt, does balance stay >= min_bal on all t >= dt?
        for d in range(91):
            cand_dt = req_date + timedelta(days=d)
            # Check all t >= cand_dt
            valid = True
            for t_d in range(d, 91):
                t_dt = req_date + timedelta(days=t_d)
                if (daily_balances[t_dt] - requested_amount) < min_bal:
                    valid = False
                    break
            if valid:
                earliest_date = cand_dt.strftime('%Y-%m-%d')
                break

    return safe_today, earliest_date, min_b_seen

print("Testing on sample requests...")
for idx, r in dl.sample_requests_df.iterrows():
    u = r['user_id']
    safe, ear, mb = simulate_user(dl, u, r['request_date'], r['requested_amount'])
    actual_safe = r['amount_safe_to_pay']
    actual_ear = r['earliest_date_for_full_payment']
    print(f"{r['request_id']} | Safe: calc={safe:.2f} vs act={actual_safe:.2f} | Earliest: calc={ear} vs act={actual_ear}")

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

FIXED_COMMITMENT_CATEGORIES = {
    'rent', 'housing', 'utilities', 'debt_repayment', 'education', 
    'insurance', 'streaming', 'cloud_storage', 'music_subscription', 
    'delivery_membership', 'gym', 'family_support'
}

def simulate_user_refined(dl, user_id, request_date_str, requested_amount):
    req_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
    end_date = req_date + timedelta(days=90)
    
    prof = dl.profiles_df.loc[user_id]
    cur_bal = float(prof['current_available_balance'])
    min_bal = float(prof['minimum_balance_to_keep'])
    adj = dl.user_adjustments.get(user_id, {})
    
    u_events = dl.events_df[dl.events_df['user_id'] == user_id].copy()
    if adj.get('ignore_events'):
        u_events = u_events[~u_events['event_id'].isin(adj['ignore_events'])]
        
    pending_debits = u_events[
        (u_events['status'].isin(['pending', 'scheduled'])) & 
        (u_events['direction'] == 'debit')
    ]
    
    # 1. Salary
    sal_events = u_events[(u_events['category'] == 'salary') & (u_events['direction'] == 'credit')]
    sal_amount = None
    sal_day = 15
    if len(sal_events) > 0:
        last_sal = sal_events.sort_values('event_date').iloc[-1]
        sal_amount = float(last_sal['amount_home_curr'])
        sal_day = datetime.strptime(str(last_sal['event_date']), '%Y-%m-%d').day
        
    if adj.get('salary_amount'):
        sal_amount = float(adj['salary_amount'])
    if adj.get('salary_date'):
        spec_date = datetime.strptime(adj['salary_date'], '%Y-%m-%d').date()
        sal_day = spec_date.day
    sal_ended = adj.get('salary_ended', False)

    settled_debits = u_events[(u_events['status'] == 'settled') & (u_events['direction'] == 'debit')].copy()
    settled_debits['dt'] = pd.to_datetime(settled_debits['event_date'])
    settled_debits['day'] = settled_debits['dt'].dt.day
    settled_debits['month'] = settled_debits['dt'].dt.to_period('M')

    # 2. Fixed recurring items
    fixed_items = []
    for cat in FIXED_COMMITMENT_CATEGORIES:
        cat_events = settled_debits[settled_debits['category'] == cat]
        if len(cat_events) >= 2:
            for desc, sub in cat_events.groupby('description'):
                if len(sub) >= 2:
                    avg_amt = float(sub['amount_home_curr'].mean())
                    common_day = sub['day'].mode().iloc[0]
                    if cat == 'rent' and adj.get('rent_multiplier', 1.0) != 1.0:
                        avg_amt *= adj['rent_multiplier']
                    fixed_items.append({
                        'desc': desc,
                        'category': cat,
                        'day': common_day,
                        'amount': avg_amt,
                        'flexibility': sub['flexibility'].iloc[-1],
                        'minimum_allowed_amount': sub['minimum_allowed_amount'].iloc[-1] if pd.notna(sub['minimum_allowed_amount'].iloc[-1]) else None,
                        'event_id': sub['event_id'].iloc[-1]
                    })

    # 3. Essential variable categories from expense_categories_to_protect
    prot_cats = set(str(prof['expense_categories_to_protect']).split('|')) - FIXED_COMMITMENT_CATEGORIES
    variable_weekly_spend = []
    for cat in prot_cats:
        cat_events = settled_debits[settled_debits['category'] == cat]
        if len(cat_events) > 0:
            monthly_totals = cat_events.groupby('month')['amount_home_curr'].sum()
            mean_monthly = float(monthly_totals.mean())
            weekly_amt = mean_monthly / 4.0
            variable_weekly_spend.append({
                'category': cat,
                'weekly_amount': weekly_amt
            })

    # Daily delta map
    daily_delta = {req_date + timedelta(days=d): 0.0 for d in range(91)}
    
    # Pending debits
    for _, pb in pending_debits.iterrows():
        s_date_str = str(pb['settlement_date']) if pd.notna(pb['settlement_date']) else str(pb['event_date'])
        s_date = datetime.strptime(s_date_str, '%Y-%m-%d').date()
        if s_date < req_date:
            daily_delta[req_date] -= float(pb['amount_home_curr'])
        elif s_date <= end_date:
            daily_delta[s_date] -= float(pb['amount_home_curr'])

    # Project salary
    if not sal_ended and sal_amount:
        curr = req_date
        while curr <= end_date:
            try:
                p_date = curr.replace(day=sal_day)
            except ValueError:
                p_date = curr.replace(day=28)
            if req_date <= p_date <= end_date:
                daily_delta[p_date] += sal_amount
            curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

    # Project fixed recurring items
    for item in fixed_items:
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

    # Project variable weekly spend (days 7, 14, 21, 28)
    for v in variable_weekly_spend:
        w_amt = v['weekly_amount']
        curr = req_date
        while curr <= end_date:
            for d_num in [7, 14, 21, 28]:
                try:
                    w_date = curr.replace(day=d_num)
                except ValueError:
                    w_date = curr.replace(day=28)
                if req_date <= w_date <= end_date:
                    daily_delta[w_date] -= w_amt
            curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

    cur_b = cur_bal
    daily_balances = {}
    for d in range(91):
        dt = req_date + timedelta(days=d)
        cur_b += daily_delta[dt]
        daily_balances[dt] = cur_b

    safe_today = max(0.0, min(requested_amount, min(daily_balances[dt] - min_bal for dt in daily_balances)))
    
    earliest_date = None
    if safe_today >= requested_amount:
        earliest_date = request_date_str
    else:
        for d in range(91):
            cand_dt = req_date + timedelta(days=d)
            if all((daily_balances[req_date + timedelta(days=t_d)] - requested_amount) >= min_bal for t_d in range(d, 91)):
                earliest_date = cand_dt.strftime('%Y-%m-%d')
                break

    return {
        'safe_today': safe_today,
        'earliest_date': earliest_date,
        'daily_balances': daily_balances,
        'min_bal': min_bal,
        'req_date': req_date,
        'fixed_items': fixed_items
    }

for idx, r in dl.sample_requests_df.iterrows():
    u = r['user_id']
    res = simulate_user_refined(dl, u, r['request_date'], r['requested_amount'])
    act_safe = r['amount_safe_to_pay']
    act_ear = r['earliest_date_for_full_payment']
    print(f"{r['request_id']} | Safe: calc={res['safe_today']:.2f} vs act={act_safe:.2f} | Ear: calc={res['earliest_date']} vs act={act_ear}")

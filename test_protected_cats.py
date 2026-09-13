import pandas as pd
from datetime import datetime, timedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

COMMITTED_CATEGORIES = {
    'rent', 'housing', 'utilities', 'debt_repayment', 'education', 
    'insurance', 'streaming', 'cloud_storage', 'music_subscription', 
    'delivery_membership', 'gym', 'family_support', 'healthcare'
}

for idx, r in dl.sample_requests_df.iterrows():
    u = r['user_id']
    req_date_str = r['request_date']
    req_date = datetime.strptime(req_date_str, '%Y-%m-%d').date()
    end_date = req_date + timedelta(days=90)
    
    prof = dl.profiles_df.loc[u]
    cur_bal = float(prof['current_available_balance'])
    min_bal = float(prof['minimum_balance_to_keep'])
    adj = dl.user_adjustments.get(u, {})
    
    # Combined recurring categories = COMMITTED_CATEGORIES + protected categories
    prot_cats = set(str(prof['expense_categories_to_protect']).split('|'))
    user_cats = COMMITTED_CATEGORIES.union(prot_cats)
    
    u_events = dl.events_df[dl.events_df['user_id'] == u].copy()
    if adj.get('ignore_events'):
        u_events = u_events[~u_events['event_id'].isin(adj['ignore_events'])]
        
    pending_debits = u_events[
        (u_events['status'].isin(['pending', 'scheduled'])) & 
        (u_events['direction'] == 'debit')
    ]
    
    # Salary
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
    
    recurring_items = []
    for cat in user_cats:
        cat_events = settled_debits[settled_debits['category'] == cat]
        if len(cat_events) >= 3:
            # Group by description
            for desc, sub in cat_events.groupby('description'):
                if len(sub) >= 3:
                    avg_amt = float(sub['amount_home_curr'].mean())
                    common_day = sub['day'].mode().iloc[0]
                    if cat == 'rent' and adj.get('rent_multiplier', 1.0) != 1.0:
                        avg_amt *= adj['rent_multiplier']
                    recurring_items.append({
                        'desc': desc,
                        'category': cat,
                        'day': common_day,
                        'amount': avg_amt
                    })

    daily_delta = {req_date + timedelta(days=d): 0.0 for d in range(91)}
    
    for _, pb in pending_debits.iterrows():
        s_date_str = str(pb['settlement_date']) if pd.notna(pb['settlement_date']) else str(pb['event_date'])
        s_date = datetime.strptime(s_date_str, '%Y-%m-%d').date()
        if s_date < req_date:
            daily_delta[req_date] -= float(pb['amount_home_curr'])
        elif s_date <= end_date:
            daily_delta[s_date] -= float(pb['amount_home_curr'])

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

    cur_b = cur_bal
    daily_balances = {}
    for d in range(91):
        dt = req_date + timedelta(days=d)
        cur_b += daily_delta[dt]
        daily_balances[dt] = cur_b

    req_amt = float(r['requested_amount'])
    safe_today = max(0.0, min(req_amt, min(daily_balances[dt] - min_bal for dt in daily_balances)))
    
    earliest_date = None
    if safe_today >= req_amt:
        earliest_date = req_date_str
    else:
        for d in range(91):
            cand_dt = req_date + timedelta(days=d)
            if all((daily_balances[req_date + timedelta(days=t_d)] - req_amt) >= min_bal for t_d in range(d, 91)):
                earliest_date = cand_dt.strftime('%Y-%m-%d')
                break

    print(f"{r['request_id']} | safe: calc={safe_today:.2f} vs act={r['amount_safe_to_pay']:.2f} | ear: calc={earliest_date} vs act={r['earliest_date_for_full_payment']}")

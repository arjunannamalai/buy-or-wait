import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

def get_user_simulation(dl, user_id, request_date_str, requested_amount):
    req_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
    end_date = req_date + timedelta(days=90)
    
    prof = dl.profiles_df.loc[user_id]
    cur_bal = float(prof['current_available_balance'])
    min_bal = float(prof['minimum_balance_to_keep'])
    adj = dl.user_adjustments.get(user_id, {})
    
    u_events = dl.events_df[dl.events_df['user_id'] == user_id].copy()
    if adj.get('ignore_events'):
        u_events = u_events[~u_events['event_id'].isin(adj['ignore_events'])]
        
    # Pending debits
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

    # Recurring debits
    settled_debits = u_events[(u_events['status'] == 'settled') & (u_events['direction'] == 'debit')].copy()
    settled_debits['dt'] = pd.to_datetime(settled_debits['event_date'])
    settled_debits['day'] = settled_debits['dt'].dt.day
    
    desc_counts = settled_debits.groupby('description').size()
    recurring_descs = desc_counts[desc_counts >= 2].index.tolist()
    
    recurring_items = []
    for desc in recurring_descs:
        sub = settled_debits[settled_debits['description'] == desc]
        avg_amt = float(sub['amount_home_curr'].mean())
        common_day = sub['day'].mode().iloc[0]
        cat = sub['category'].iloc[0]
        
        if cat == 'rent' and adj.get('rent_multiplier', 1.0) != 1.0:
            avg_amt *= adj['rent_multiplier']
            
        recurring_items.append({
            'desc': desc,
            'category': cat,
            'day': common_day,
            'amount': avg_amt,
            'flexibility': sub['flexibility'].iloc[-1],
            'event_id': sub['event_id'].iloc[-1]
        })
        
    # Build daily net changes over 90 days
    daily_delta = {req_date + timedelta(days=d): 0.0 for d in range(91)}
    
    for idx, r in pending_debits.iterrows():
        s_date_str = str(r['settlement_date']) if pd.notna(r['settlement_date']) else str(r['event_date'])
        s_date = datetime.strptime(s_date_str, '%Y-%m-%d').date()
        if s_date < req_date:
            daily_delta[req_date] -= float(r['amount_home_curr'])
        elif s_date <= end_date:
            daily_delta[s_date] -= float(r['amount_home_curr'])

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

    safe_today = max(0.0, min(requested_amount, min(daily_balances[dt] - min_bal for dt in daily_balances)))
    
    earliest_date = None
    if safe_today >= requested_amount:
        earliest_date = request_date_str
    else:
        for d in range(91):
            cand_dt = req_date + timedelta(days=d)
            valid = True
            for t_d in range(d, 91):
                t_dt = req_date + timedelta(days=t_d)
                if (daily_balances[t_dt] - requested_amount) < min_bal:
                    valid = False
                    break
            if valid:
                earliest_date = cand_dt.strftime('%Y-%m-%d')
                break

    return {
        'safe_today': safe_today,
        'earliest_date': earliest_date,
        'daily_balances': daily_balances,
        'min_bal': min_bal,
        'recurring_items': recurring_items,
        'req_date': req_date,
        'end_date': end_date
    }

print("Running planner evaluator...")

for idx, r in dl.sample_requests_df.iterrows():
    req_id = r['request_id']
    u = r['user_id']
    req_date_str = r['request_date']
    req_amt = float(r['requested_amount'])
    due_date_str = r['desired_completion_date']
    allow_partial = bool(r['allows_partial_payment'])
    
    prof = dl.profiles_df.loc[u]
    allowed_methods = str(prof['payment_methods_user_will_consider']).split('|')
    max_inst = prof['max_installment_months']
    if pd.isna(max_inst):
        max_inst = None
    else:
        max_inst = float(max_inst)

    # Use actual safe_today and earliest_date from sample to test planner ranking logic
    # (or test both)
    act_safe = float(r['amount_safe_to_pay'])
    act_ear = r['earliest_date_for_full_payment']
    
    opts = dl.payment_options_df[dl.payment_options_df['request_id'] == req_id]
    
    # 1. Candidate: full payment today
    candidates = []
    if 'full_payment' in allowed_methods and act_safe >= req_amt:
        candidates.append({
            'status': 'affordable_now',
            'method': 'full_payment',
            'plan': f"{req_date_str}:{int(req_amt) if req_amt.is_integer() else req_amt:.2f}",
            'spending': 'none',
            'total_amt': req_amt,
            'start_date': req_date_str,
            'num_payments': 1,
            'opt_id': 'option_00',
            'completes_on_time': True
        })

    # 2. Candidate: partial payment
    if allow_partial and 'partial_payment' in allowed_methods and 0 < act_safe < req_amt and pd.notna(act_ear) and act_ear <= due_date_str:
        p1 = int(act_safe) if act_safe.is_integer() else act_safe
        rem = req_amt - act_safe
        p2 = int(rem) if rem.is_integer() else rem
        candidates.append({
            'status': 'affordable_with_plan',
            'method': 'partial_payment',
            'plan': f"{req_date_str}:{p1}|{act_ear}:{p2}",
            'spending': 'none',
            'total_amt': req_amt,
            'start_date': req_date_str,
            'num_payments': 2,
            'opt_id': 'option_00',
            'completes_on_time': True
        })

    # 3. Candidate: installments
    if 'installments' in allowed_methods:
        for o_idx, o in opts[opts['payment_method'] == 'installments'].iterrows():
            n_pay = int(o['number_of_payments'])
            if max_inst is not None and n_pay > max_inst:
                continue
            first_date = datetime.strptime(o['first_payment_date'], '%Y-%m-%d').date()
            freq = int(o['payment_frequency_days'])
            dates = [first_date + timedelta(days=i*freq) for i in range(n_pay)]
            last_date_str = dates[-1].strftime('%Y-%m-%d')
            completes_on_time = (last_date_str <= due_date_str)
            
            p_amt = float(o['payment_amount'])
            p_amt_str = f"{p_amt:.2f}" if (p_amt % 1 != 0) else f"{int(p_amt)}"
            plan_str = "|".join(f"{d.strftime('%Y-%m-%d')}:{p_amt_str}" for d in dates)
            
            candidates.append({
                'status': 'affordable_with_plan',
                'method': 'installments',
                'plan': plan_str,
                'spending': 'none',
                'total_amt': float(o['total_payable_amount']),
                'start_date': o['first_payment_date'],
                'num_payments': n_pay,
                'opt_id': o['payment_option_id'],
                'completes_on_time': completes_on_time
            })

    # 4. Candidate: wait
    if 'full_payment' in allowed_methods and pd.notna(act_ear):
        completes_on_time = (act_ear <= due_date_str)
        candidates.append({
            'status': 'affordable_later',
            'method': 'wait',
            'plan': f"{act_ear}:{int(req_amt) if req_amt.is_integer() else req_amt:.2f}",
            'spending': 'none',
            'total_amt': req_amt,
            'start_date': act_ear,
            'num_payments': 1,
            'opt_id': 'option_99',
            'completes_on_time': completes_on_time
        })

    # Filter candidates that complete on time
    on_time_candidates = [c for c in candidates if c['completes_on_time']]
    
    # Check if actual sample had spending changes
    actual_spending = r['spending_changes_needed']
    
    print(f"=== {req_id} ({u}) ===")
    print(f"  ACTUAL: status={r['affordability_status']}, method={r['recommended_payment_method']}, plan={r['payment_plan']}")
    print(f"  Available on-time candidates: {len(on_time_candidates)}")
    for c in on_time_candidates:
        print(f"    cand: {c['method']} | tot: {c['total_amt']} | start: {c['start_date']} | n: {c['num_payments']} | opt: {c['opt_id']}")
        print(f"          plan: {c['plan']}")

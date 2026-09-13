"""
Refined Forecast Engine for 90-Day Cash Flow Simulation.
Accurately models fixed monthly commitments, essential weekly protected living expenses,
confirmed salary schedules, and checks safety constraints on every day of the 90-day window.
"""

import pandas as pd
import numpy as np
import calendar
from datetime import datetime, timedelta

FIXED_COMMITMENT_CATEGORIES = {
    'rent', 'housing', 'utilities', 'debt_repayment', 'education', 
    'insurance', 'streaming', 'cloud_storage', 'music_subscription', 
    'delivery_membership', 'gym', 'family_support', 'healthcare'
}

RECURRING_SALARY_DESCRIPTIONS = {
    'payroll credit', 'base salary', 'international employer payroll',
    'primary household salary', 'first-job payroll', 'new employer payroll',
    'payroll after returning from leave', 'prorated first salary',
    'next confirmed salary', 'second household income'
}

class ForecastEngine:
    def __init__(self, data_loader):
        self.dl = data_loader

    def get_user_timeline(self, user_id, request_date_str):
        req_date = datetime.strptime(request_date_str, '%Y-%m-%d').date()
        end_date = req_date + timedelta(days=90)
        
        prof = self.dl.profiles_df.loc[user_id]
        cur_bal = float(prof['current_available_balance'])
        min_bal = float(prof['minimum_balance_to_keep'])
        adj = self.dl.user_adjustments.get(user_id, {})
        
        u_events = self.dl.events_df[self.dl.events_df['user_id'] == user_id].copy()
        if adj.get('ignore_events'):
            u_events = u_events[~u_events['event_id'].isin(adj['ignore_events'])]
            
        # 1. Pending debits (ignore duplicate charges per challenge spec)
        pending_debits = u_events[
            (u_events['status'].isin(['pending', 'scheduled'])) & 
            (u_events['direction'] == 'debit') &
            (~u_events['description'].str.contains('duplicate', case=False, na=False))
        ]
        
        # 2. Confirmed recurring salary streams
        sal_events = u_events[(u_events['category'] == 'salary') & (u_events['direction'] == 'credit')].copy()
        sal_ended = adj.get('salary_ended', False)

        # Check if employment has ended based on final payroll event
        if len(sal_events) > 0:
            last_sal_overall = sal_events.sort_values('event_date').iloc[-1]
            sal_desc_overall = str(last_sal_overall['description']).lower()
            if 'final employer payroll' in sal_desc_overall or 'last payroll' in sal_desc_overall:
                sal_ended = True

        salary_streams = []

        if not sal_ended:
            if adj.get('salary_amount') is not None:
                # Explicit override from parsed message
                s_day = 15
                if adj.get('salary_date'):
                    s_day = datetime.strptime(adj['salary_date'], '%Y-%m-%d').date().day
                elif len(sal_events) > 0:
                    base_sals = sal_events[sal_events['description'].astype(str).str.lower().isin(RECURRING_SALARY_DESCRIPTIONS)]
                    last_ev = base_sals.sort_values('event_date').iloc[-1] if len(base_sals) > 0 else sal_events.sort_values('event_date').iloc[-1]
                    s_day = datetime.strptime(str(last_ev['event_date']), '%Y-%m-%d').day
                salary_streams.append({'amount': float(adj['salary_amount']), 'day': s_day})
            else:
                # Whitelist confirmed recurring salary streams
                valid_sals = sal_events[sal_events['description'].astype(str).str.lower().isin(RECURRING_SALARY_DESCRIPTIONS)]
                if len(valid_sals) > 0:
                    sec_inc = valid_sals[valid_sals['description'].astype(str).str.lower() == 'second household income']
                    prim_inc = valid_sals[valid_sals['description'].astype(str).str.lower().isin(['primary household salary', 'next confirmed salary'])]
                    if len(prim_inc) > 0 and len(sec_inc) > 0:
                        # Dual income household
                        last_prim = prim_inc.sort_values('event_date').iloc[-1]
                        p_amt = float(last_prim['amount_home_curr'])
                        p_day = datetime.strptime(str(last_prim['event_date']), '%Y-%m-%d').day
                        salary_streams.append({'amount': p_amt, 'day': p_day})

                        s_amt = float(sec_inc['amount_home_curr'].mean())
                        s_day = datetime.strptime(str(sec_inc.sort_values('event_date').iloc[-1]['event_date']), '%Y-%m-%d').day
                        salary_streams.append({'amount': s_amt, 'day': s_day})
                    else:
                        last_sal = valid_sals.sort_values('event_date').iloc[-1]
                        sal_desc = str(last_sal['description']).lower()
                        if 'final employer payroll' in sal_desc:
                            sal_ended = True
                        else:
                            amt = float(last_sal['amount_home_curr'])
                            s_day = datetime.strptime(str(last_sal['event_date']), '%Y-%m-%d').day
                            if adj.get('salary_date'):
                                s_day = datetime.strptime(adj['salary_date'], '%Y-%m-%d').date().day
                            salary_streams.append({'amount': amt, 'day': s_day})

        # 3. Fixed recurring items
        settled_debits = u_events[(u_events['status'] == 'settled') & (u_events['direction'] == 'debit')].copy()
        settled_debits['dt'] = pd.to_datetime(settled_debits['event_date'])
        settled_debits['day'] = settled_debits['dt'].dt.day
        settled_debits['month'] = settled_debits['dt'].dt.to_period('M')

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

        # All flexible items for potential spending adjustments
        all_flexible_items = []
        for _, r in settled_debits.iterrows():
            if r['flexibility'] in ['reducible', 'stoppable', 'reducible_or_stoppable']:
                all_flexible_items.append({
                    'event_id': r['event_id'],
                    'category': r['category'],
                    'description': r['description'],
                    'amount': float(r['amount_home_curr']),
                    'flexibility': r['flexibility'],
                    'minimum_allowed_amount': float(r['minimum_allowed_amount']) if pd.notna(r['minimum_allowed_amount']) else None
                })

        # 4. Essential variable categories: protect categories + base living categories (groceries, transport)
        prot_cats = (set(str(prof['expense_categories_to_protect']).split('|')) | {'groceries', 'transport'}) - FIXED_COMMITMENT_CATEGORIES
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
        
        # Apply pending debits
        for _, pb in pending_debits.iterrows():
            s_date_str = str(pb['settlement_date']) if pd.notna(pb['settlement_date']) else str(pb['event_date'])
            s_date = datetime.strptime(s_date_str, '%Y-%m-%d').date()
            if s_date < req_date:
                daily_delta[req_date] -= float(pb['amount_home_curr'])
            elif s_date <= end_date:
                daily_delta[s_date] -= float(pb['amount_home_curr'])

        # Project salary streams with proper month-end clamping
        if not sal_ended:
            for stream in salary_streams:
                s_amt = stream['amount']
                s_day = stream['day']
                curr = req_date
                while curr <= end_date:
                    max_d = calendar.monthrange(curr.year, curr.month)[1]
                    p_date = curr.replace(day=min(s_day, max_d))
                    if req_date <= p_date <= end_date:
                        daily_delta[p_date] += s_amt
                    curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

        # Project fixed recurring items with proper month-end clamping
        for item in fixed_items:
            amt = item['amount']
            day = item['day']
            curr = req_date
            while curr <= end_date:
                max_d = calendar.monthrange(curr.year, curr.month)[1]
                d_date = curr.replace(day=min(day, max_d))
                if req_date <= d_date <= end_date:
                    daily_delta[d_date] -= amt
                curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

        # Project variable weekly spend (days 7, 14, 21, 28)
        for v in variable_weekly_spend:
            w_amt = v['weekly_amount']
            curr = req_date
            while curr <= end_date:
                max_d = calendar.monthrange(curr.year, curr.month)[1]
                for d_num in [7, 14, 21, 28]:
                    w_date = curr.replace(day=min(d_num, max_d))
                    if req_date <= w_date <= end_date:
                        daily_delta[w_date] -= w_amt
                curr = (curr.replace(day=1) + timedelta(days=32)).replace(day=1)

        # Calculate base daily balances B(t)
        cur_b = cur_bal
        daily_balances = {}
        for d in range(91):
            dt = req_date + timedelta(days=d)
            cur_b += daily_delta[dt]
            daily_balances[dt] = cur_b

        return {
            'req_date': req_date,
            'end_date': end_date,
            'cur_bal': cur_bal,
            'min_bal': min_bal,
            'daily_balances': daily_balances,
            'fixed_items': fixed_items,
            'all_flexible_items': all_flexible_items,
            'prof': prof,
            'sal_day': salary_streams[0]['day'] if salary_streams else 15,
            'salary_streams': salary_streams
        }

    def compute_metrics(self, user_id, request_date_str, requested_amount):
        tl = self.get_user_timeline(user_id, request_date_str)
        daily_balances = tl['daily_balances']
        min_bal = tl['min_bal']
        req_date = tl['req_date']
        
        min_headroom = min(daily_balances[dt] - min_bal for dt in daily_balances)
        safe_today = max(0.0, min(requested_amount, min_headroom))
        
        earliest_date = None
        if safe_today >= requested_amount:
            earliest_date = request_date_str
        else:
            for d in range(91):
                cand_dt = req_date + timedelta(days=d)
                if all((daily_balances[req_date + timedelta(days=t_d)] - requested_amount) >= min_bal for t_d in range(d, 91)):
                    earliest_date = cand_dt.strftime('%Y-%m-%d')
                    break

        return safe_today, earliest_date, tl

    def is_schedule_safe(self, timeline, schedule):
        daily_balances = timeline['daily_balances']
        min_bal = timeline['min_bal']
        req_date = timeline['req_date']
        
        pay_map = {dt: 0.0 for dt in daily_balances}
        for p_date, p_amt in schedule:
            if p_date in pay_map:
                pay_map[p_date] += p_amt
            elif p_date < req_date:
                pay_map[req_date] += p_amt
                
        cum_pay = 0.0
        for d in range(91):
            dt = req_date + timedelta(days=d)
            cum_pay += pay_map[dt]
            # Small tolerance for floating point rounding (0.01)
            if (daily_balances[dt] - cum_pay) < (min_bal - 0.01):
                return False
        return True

    def evaluate_spending_changes(self, timeline, requested_amount):
        prof = timeline['prof']
        min_bal = timeline['min_bal']
        daily_balances = timeline['daily_balances']
        
        stop_cats = set(str(prof['expense_categories_user_is_willing_to_stop']).split('|'))
        red_cats = set(str(prof['expense_categories_user_is_willing_to_reduce']).split('|'))
        prot_cats = set(str(prof['expense_categories_to_protect']).split('|'))
        
        # Candidate events must not be in protected categories
        stop_cats = stop_cats - prot_cats
        red_cats = red_cats - prot_cats
        
        candidates = []
        seen = set()
        for item in reversed(timeline['all_flexible_items']):
            evt_id = item['event_id']
            if evt_id in seen:
                continue
            seen.add(evt_id)
            
            cat = item['category']
            flex = item['flexibility']
            amt = item['amount']
            min_amt = item['minimum_allowed_amount']
            
            if cat in stop_cats and flex in ['stoppable', 'reducible_or_stoppable']:
                candidates.append({
                    'type': 'stop',
                    'event_id': evt_id,
                    'desc': item['description'],
                    'savings': amt,
                    'projected_savings': amt * 2.0,
                    'action': f"stop:{evt_id}"
                })
            if cat in red_cats and flex in ['reducible', 'reducible_or_stoppable']:
                if min_amt is not None and min_amt < amt:
                    savings = amt - min_amt
                    min_str = int(min_amt) if round(min_amt, 2) == round(min_amt, 0) else f"{min_amt:.2f}"
                    candidates.append({
                        'type': 'reduce',
                        'event_id': evt_id,
                        'desc': item['description'],
                        'savings': savings,
                        'projected_savings': savings * 2.0,
                        'action': f"reduce_to:{evt_id}:{min_str}"
                    })
                    
        min_headroom = min(daily_balances[dt] - min_bal for dt in daily_balances)
        shortfall = requested_amount - min_headroom
        
        if shortfall <= 0:
            return True, 'none'
            
        # 1. Single action with projected multi-month savings
        for c in candidates:
            if c['projected_savings'] >= shortfall:
                return True, c['action']
                
        # 2. Pair of distinct actions
        for i in range(len(candidates)):
            for j in range(i+1, len(candidates)):
                c1, c2 = candidates[i], candidates[j]
                if c1['event_id'] == c2['event_id'] or c1['desc'].lower() == c2['desc'].lower():
                    continue
                if (c1['projected_savings'] + c2['projected_savings']) >= shortfall:
                    return True, f"{c1['action']}|{c2['action']}"
                    
        # 3. Triple of distinct actions
        for i in range(len(candidates)):
            for j in range(i+1, len(candidates)):
                for k in range(j+1, len(candidates)):
                    c1, c2, c3 = candidates[i], candidates[j], candidates[k]
                    e_ids = {c1['event_id'], c2['event_id'], c3['event_id']}
                    descs = {c1['desc'].lower(), c2['desc'].lower(), c3['desc'].lower()}
                    if len(e_ids) < 3 or len(descs) < 3:
                        continue
                    if (c1['projected_savings'] + c2['projected_savings'] + c3['projected_savings']) >= shortfall:
                        return True, f"{c1['action']}|{c2['action']}|{c3['action']}"
                        
        return False, 'none'

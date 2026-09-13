"""
Planner module that evaluates eligible payment methods and ranks candidate plans
according to the contest tie-breaking hierarchy.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def fmt_amount(amt):
    amt_rounded = round(float(amt), 2)
    if amt_rounded == int(amt_rounded):
        return str(int(amt_rounded))
    return f"{amt_rounded:.2f}"

class Planner:
    def __init__(self, data_loader, forecast_engine):
        self.dl = data_loader
        self.engine = forecast_engine

    def evaluate_request(self, request_row):
        req_id = request_row['request_id']
        u = request_row['user_id']
        req_date_str = str(request_row['request_date'])
        req_amt = float(request_row['requested_amount'])
        due_date_str = str(request_row['desired_completion_date'])
        allow_partial = bool(request_row['allows_partial_payment'])

        prof = self.dl.profiles_df.loc[u]
        allowed_methods = str(prof['payment_methods_user_will_consider']).split('|')
        max_inst = prof['max_installment_months']
        max_inst = float(max_inst) if pd.notna(max_inst) else None

        # 1. Compute safe_today, earliest_date, and timeline
        safe_today, earliest_date, timeline = self.engine.compute_metrics(u, req_date_str, req_amt)
        safe_today = round(safe_today, 2)

        # Retrieve payment options
        opts = self.dl.payment_options_df[self.dl.payment_options_df['request_id'] == req_id]

        candidates = []

        # -------------------------------------------------------------
        # Candidate 1: Full payment today without spending changes
        # -------------------------------------------------------------
        if 'full_payment' in allowed_methods and safe_today >= req_amt:
            p_str = f"{req_date_str}:{fmt_amount(req_amt)}"
            candidates.append({
                'status': 'affordable_now',
                'method': 'full_payment',
                'plan': p_str,
                'spending': 'none',
                'total_amt': req_amt,
                'start_date': req_date_str,
                'num_payments': 1,
                'opt_id': 'option_00',
                'completes_on_time': (req_date_str <= due_date_str),
                'needs_spending_changes': False
            })

        # -------------------------------------------------------------
        # Candidate 2: Partial payment without spending changes
        # -------------------------------------------------------------
        if (allow_partial and 
            'partial_payment' in allowed_methods and 
            0 < safe_today < req_amt and 
            earliest_date is not None and 
            earliest_date <= due_date_str):
            
            p1_str = fmt_amount(safe_today)
            rem = round(req_amt - safe_today, 2)
            p2_str = fmt_amount(rem)
            plan_str = f"{req_date_str}:{p1_str}|{earliest_date}:{p2_str}"
            candidates.append({
                'status': 'affordable_with_plan',
                'method': 'partial_payment',
                'plan': plan_str,
                'spending': 'none',
                'total_amt': req_amt,
                'start_date': req_date_str,
                'num_payments': 2,
                'opt_id': 'option_00',
                'completes_on_time': True,
                'needs_spending_changes': False
            })

        # -------------------------------------------------------------
        # Candidate 3: Installments
        # -------------------------------------------------------------
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

                # Check schedule safety
                p_amt = float(o['payment_amount'])
                schedule = [(d, p_amt) for d in dates]
                if self.engine.is_schedule_safe(timeline, schedule):
                    p_amt_str = fmt_amount(p_amt)
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
                        'completes_on_time': completes_on_time,
                        'needs_spending_changes': False
                    })

        # -------------------------------------------------------------
        # Candidate 4: Full payment with spending changes
        # -------------------------------------------------------------
        if 'full_payment' in allowed_methods and safe_today < req_amt:
            can_fix, spending_str = self.engine.evaluate_spending_changes(timeline, req_amt)
            if can_fix and spending_str != 'none':
                p_str = f"{req_date_str}:{fmt_amount(req_amt)}"
                candidates.append({
                    'status': 'affordable_with_plan',
                    'method': 'full_payment',
                    'plan': p_str,
                    'spending': spending_str,
                    'total_amt': req_amt,
                    'start_date': req_date_str,
                    'num_payments': 1,
                    'opt_id': 'option_00',
                    'completes_on_time': (req_date_str <= due_date_str),
                    'needs_spending_changes': True
                })

        # -------------------------------------------------------------
        # Candidate 5: Wait (full payment on earliest_date_for_full_payment)
        # -------------------------------------------------------------
        if 'full_payment' in allowed_methods and earliest_date is not None:
            completes_on_time = (earliest_date <= due_date_str)
            p_str = f"{earliest_date}:{fmt_amount(req_amt)}"
            candidates.append({
                'status': 'affordable_later',
                'method': 'wait',
                'plan': p_str,
                'spending': 'none',
                'total_amt': req_amt,
                'start_date': earliest_date,
                'num_payments': 1,
                'opt_id': 'option_99',
                'completes_on_time': completes_on_time,
                'needs_spending_changes': False
            })

        # Filter and rank candidates
        # Tie-breaking priority:
        # 1. Complete full request by desired_completion_date
        # 2. Require no spending changes
        # 3. Minimize total amount paid
        # 4. Start payment earlier
        # 5. Use fewer payments
        # 6. Lowest payment_option_id
        def sort_key(c):
            return (
                0 if c['completes_on_time'] else 1,
                1 if c['needs_spending_changes'] else 0,
                c['total_amt'],
                c['start_date'],
                c['num_payments'],
                c['opt_id']
            )

        candidates.sort(key=sort_key)

        # Select best plan
        best = None
        for c in candidates:
            if c['completes_on_time']:
                best = c
                break

        if best is None and candidates:
            # If none completes on time, check if wait is safe later
            for c in candidates:
                if c['method'] == 'wait':
                    best = c
                    break

        if best is None:
            # Fallback: not_affordable
            return {
                'request_id': req_id,
                'amount_safe_to_pay': safe_today,
                'affordability_status': 'not_affordable',
                'recommended_payment_method': 'not_recommended',
                'payment_plan': 'none',
                'earliest_date_for_full_payment': '',
                'spending_changes_needed': 'none'
            }
        else:
            return {
                'request_id': req_id,
                'amount_safe_to_pay': safe_today,
                'affordability_status': best['status'],
                'recommended_payment_method': best['method'],
                'payment_plan': best['plan'],
                'earliest_date_for_full_payment': earliest_date if earliest_date else '',
                'spending_changes_needed': best['spending']
            }

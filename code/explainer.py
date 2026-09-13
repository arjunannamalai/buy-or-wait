"""
Explainer module generating grounded, concise decision explanations.
Matches the benchmark style and format from dataset/sample_requests.csv.
"""

from datetime import datetime
import pandas as pd

def format_date_natural(date_str):
    if not date_str or pd.isna(date_str):
        return ""
    dt = datetime.strptime(str(date_str), '%Y-%m-%d')
    months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    return f"{dt.day} {months[dt.month]} {dt.year}"

def format_currency_amount(amount):
    if round(amount, 2) == round(amount, 0):
        return f"{int(round(amount)):,}"
    else:
        return f"{amount:,.2f}"

class DecisionExplainer:
    def __init__(self, data_loader):
        self.dl = data_loader

    def generate_explanation(self, request_row, decision):
        u = request_row['user_id']
        prof = self.dl.profiles_df.loc[u]
        curr = prof['home_currency']
        min_bal = float(prof['minimum_balance_to_keep'])
        min_bal_str = format_currency_amount(min_bal)
        req_amt = float(request_row['requested_amount'])
        req_amt_str = format_currency_amount(req_amt)
        
        status = decision['affordability_status']
        method = decision['recommended_payment_method']
        plan = decision['payment_plan']
        earliest_date = decision['earliest_date_for_full_payment']
        spending = decision['spending_changes_needed']
        due_date = request_row['desired_completion_date']
        due_date_str = format_date_natural(due_date)

        # 1. affordable_now with full_payment
        if status == 'affordable_now' and method == 'full_payment':
            return f"Pay {curr} {req_amt_str} today. This leaves at least {curr} {min_bal_str} available over the next 90 days."

        # 2. affordable_with_plan with installments
        if method == 'installments' and plan != 'none':
            parts = plan.split('|')
            n_inst = len(parts)
            first_part = parts[0]
            first_dt_str, first_amt_str = first_part.split(':')
            inst_amt = float(first_amt_str)
            inst_amt_fmt = format_currency_amount(inst_amt)
            start_date_fmt = format_date_natural(first_dt_str)
            return f"Use {n_inst} installments of {curr} {inst_amt_fmt}, starting {start_date_fmt}. This leaves at least {curr} {min_bal_str} available."

        # 3. affordable_with_plan with partial_payment
        if method == 'partial_payment' and plan != 'none':
            parts = plan.split('|')
            p1_amt = float(parts[0].split(':')[1])
            p2_date = parts[1].split(':')[0]
            p2_amt = float(parts[1].split(':')[1])
            return (f"Pay {curr} {format_currency_amount(p1_amt)} today and the remaining "
                    f"{curr} {format_currency_amount(p2_amt)} on {format_date_natural(p2_date)}. "
                    f"This completes the full request and keeps the {curr} {min_bal_str} minimum protected.")

        # 4. affordable_with_plan with full_payment and spending changes
        if method == 'full_payment' and spending != 'none':
            actions = spending.split('|')
            desc_parts = []
            for act in actions:
                if act.startswith('stop:'):
                    e_id = act.split(':')[1]
                    # find event description
                    evts = self.dl.events_df[self.dl.events_df['event_id'] == e_id]
                    e_desc = evts['description'].iloc[0].lower() if len(evts) > 0 else 'expense'
                    desc_parts.append(f"Stop the {e_desc}")
                elif act.startswith('reduce_to:'):
                    e_id = act.split(':')[1]
                    n_amt = float(act.split(':')[2])
                    evts = self.dl.events_df[self.dl.events_df['event_id'] == e_id]
                    e_desc = evts['description'].iloc[0].lower() if len(evts) > 0 else 'expense'
                    desc_parts.append(f"Reduce the {e_desc} to {curr} {format_currency_amount(n_amt)}")
            
            spending_clause = " and ".join(desc_parts)
            return f"{spending_clause}, then pay {curr} {req_amt_str} today. This leaves at least {curr} {min_bal_str} available."

        # 5. affordable_later with wait
        if method == 'wait' and earliest_date:
            ear_fmt = format_date_natural(earliest_date)
            return f"Pay {curr} {req_amt_str} in full on {ear_fmt}. Paying earlier would take the balance below the {curr} {min_bal_str} minimum."

        # 6. not_affordable / not_recommended
        safe_today = decision['amount_safe_to_pay']
        allowed_methods = str(prof['payment_methods_user_will_consider']).split('|')
        if 'full_payment' not in allowed_methods and safe_today >= req_amt:
            return f"Do not proceed with the {curr} {req_amt_str} request by {due_date_str}. While funds are available for a full payment, only installments are accepted, and available installment options add financing fees that take the balance below the {curr} {min_bal_str} minimum."
        elif safe_today > 0 and (not earliest_date or pd.isna(earliest_date) or earliest_date == ''):
            return (f"Do not proceed with the {curr} {req_amt_str} request. "
                    f"Although {curr} {format_currency_amount(safe_today)} is available today, "
                    f"the full amount cannot be completed safely within 90 days.")
        else:
            return f"Do not make this payment by {due_date_str}. None of the available options keeps the {curr} {min_bal_str} minimum protected."

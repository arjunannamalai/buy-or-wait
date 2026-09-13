"""
Data loader and preprocessor for the Buy or Wait challenge.
Loads profiles, events, exchange rates, payment options, and requests,
applies OCR values and currency conversions, and structures the data for simulation.
"""

import pandas as pd
import numpy as np
from code.ocr_data import OCR_EVENT_AMOUNTS
from code.messages_parser import parse_messages

class DataLoader:
    def __init__(self, dataset_dir='dataset'):
        self.dataset_dir = dataset_dir
        self.profiles_df = None
        self.events_df = None
        self.exchange_rates_df = None
        self.payment_options_df = None
        self.requests_df = None
        self.sample_requests_df = None
        self.user_adjustments = None
        self.exchange_map = {}

    def load_all(self):
        # 1. Load profiles
        self.profiles_df = pd.read_csv(f'{self.dataset_dir}/financial_profiles.csv').set_index('user_id')

        # 2. Load exchange rates
        self.exchange_rates_df = pd.read_csv(f'{self.dataset_dir}/exchange_rates.csv')
        for idx, r in self.exchange_rates_df.iterrows():
            key = (r['rate_date'], r['from_currency'], r['to_currency'])
            self.exchange_map[key] = float(r['rate'])

        # 3. Load message adjustments
        self.user_adjustments = parse_messages(f'{self.dataset_dir}/messages.csv')

        # 4. Load financial events
        self.events_df = pd.read_csv(f'{self.dataset_dir}/financial_events.csv')
        
        # Apply OCR amounts
        for evt_id, amt in OCR_EVENT_AMOUNTS.items():
            self.events_df.loc[self.events_df['event_id'] == evt_id, 'amount'] = amt

        # Convert foreign currency events to user's home currency
        self._convert_event_currencies()

        # Convert message salary adjustments to home currency if needed
        for u, adj in self.user_adjustments.items():
            if adj.get('salary_amount') and adj.get('salary_currency'):
                if u in self.profiles_df.index:
                    home_curr = self.profiles_df.loc[u, 'home_currency']
                    s_curr = adj['salary_currency']
                    if s_curr != home_curr:
                        s_date = adj.get('salary_date') or '2025-01-01'
                        rate = self.get_exchange_rate(str(s_date), s_curr, home_curr)
                        adj['salary_amount'] = round(adj['salary_amount'] * rate, 2)

        # 5. Load payment options
        self.payment_options_df = pd.read_csv(f'{self.dataset_dir}/request_payment_options.csv')

        # 6. Load requests
        self.requests_df = pd.read_csv(f'{self.dataset_dir}/requests.csv')
        self.sample_requests_df = pd.read_csv(f'{self.dataset_dir}/sample_requests.csv')

        return self

    def get_exchange_rate(self, date_str, from_curr, to_curr):
        if from_curr == to_curr:
            return 1.0
        
        # Exact date match
        if (date_str, from_curr, to_curr) in self.exchange_map:
            return self.exchange_map[(date_str, from_curr, to_curr)]
        if (date_str, to_curr, from_curr) in self.exchange_map:
            return 1.0 / self.exchange_map[(date_str, to_curr, from_curr)]

        # Find closest date for this pair
        matching = self.exchange_rates_df[
            ((self.exchange_rates_df['from_currency'] == from_curr) & (self.exchange_rates_df['to_currency'] == to_curr)) |
            ((self.exchange_rates_df['from_currency'] == to_curr) & (self.exchange_rates_df['to_currency'] == from_curr))
        ]
        if len(matching) > 0:
            # Sort by date
            matching = matching.sort_values('rate_date')
            r = matching.iloc[-1]
            if r['from_currency'] == from_curr and r['to_currency'] == to_curr:
                return float(r['rate'])
            else:
                return 1.0 / float(r['rate'])

        return 1.0

    def _convert_event_currencies(self):
        home_currencies = self.profiles_df['home_currency'].to_dict()
        
        converted_amounts = []
        for idx, r in self.events_df.iterrows():
            u = r['user_id']
            home_curr = home_currencies.get(u, r['currency'])
            evt_curr = r['currency']
            amt = r['amount']

            if pd.isna(amt):
                converted_amounts.append(np.nan)
                continue

            if evt_curr == home_curr:
                converted_amounts.append(float(amt))
            else:
                settle_date = r['settlement_date'] if pd.notna(r['settlement_date']) else r['event_date']
                rate = self.get_exchange_rate(str(settle_date), evt_curr, home_curr)
                converted_amounts.append(float(amt) * rate)

        self.events_df['amount_home_curr'] = converted_amounts

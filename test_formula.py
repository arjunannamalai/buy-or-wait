import pandas as pd
import numpy as np
import datetime
from collections import defaultdict

profiles_df = pd.read_csv('dataset/financial_profiles.csv').set_index('user_id')
events_df = pd.read_csv('dataset/financial_events.csv')
sample_df = pd.read_csv('dataset/sample_requests.csv')
options_df = pd.read_csv('dataset/request_payment_options.csv')

print("Loaded datasets for testing formula.")

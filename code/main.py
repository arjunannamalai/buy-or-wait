"""
Main entrypoint for HackerRank Orchestrate: Buy or Wait?
Generates final predictions for dataset/requests.csv and outputs output.csv.
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime

# Ensure project directory is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code.data_loader import DataLoader
from code.forecast_engine import ForecastEngine
from code.planner import Planner, fmt_amount
from code.explainer import DecisionExplainer

def run_pipeline(dataset_dir="dataset", output_csv_path="output.csv"):
    start_time = datetime.now()
    print(f"[{start_time.isoformat()}] Starting Buy or Wait? financial decision engine...")
    print(f"Loading datasets from: {dataset_dir}")
    
    dl = DataLoader(dataset_dir)
    dl.load_all()
    print(f"Loaded {len(dl.profiles_df)} profiles, {len(dl.events_df)} financial events, {len(dl.requests_df)} requests.")
    
    engine = ForecastEngine(dl)
    planner = Planner(dl, engine)
    explainer = DecisionExplainer(dl)
    
    requests_df = dl.requests_df
    results = []
    
    print(f"Evaluating {len(requests_df)} requests...")
    for idx, row in requests_df.iterrows():
        req_id = row['request_id']
        decision = planner.evaluate_request(row)
        explanation = explainer.generate_explanation(row, decision)
        
        # Ensure proper rounding and formatting
        safe_pay_str = fmt_amount(decision['amount_safe_to_pay'])
            
        earliest_date = decision['earliest_date_for_full_payment']
        if pd.isna(earliest_date) or earliest_date is None:
            earliest_date = ""
            
        results.append({
            'request_id': req_id,
            'amount_safe_to_pay': safe_pay_str,
            'affordability_status': decision['affordability_status'],
            'recommended_payment_method': decision['recommended_payment_method'],
            'payment_plan': decision['payment_plan'],
            'earliest_date_for_full_payment': earliest_date,
            'spending_changes_needed': decision['spending_changes_needed'],
            'decision_explanation': explanation
        })
        
    out_df = pd.DataFrame(results)
    
    # Required columns in exact order
    columns_order = [
        'request_id',
        'amount_safe_to_pay',
        'affordability_status',
        'recommended_payment_method',
        'payment_plan',
        'earliest_date_for_full_payment',
        'spending_changes_needed',
        'decision_explanation'
    ]
    out_df = out_df[columns_order]
    
    # Write to target CSV
    out_df.to_csv(output_csv_path, index=False)
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"[{end_time.isoformat()}] Finished in {duration:.2f}s.")
    print(f"Output saved to: {output_csv_path} ({len(out_df)} rows).")
    return out_df

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Run Buy or Wait? financial agent.")
    parser.add_argument("--dataset_dir", type=str, default="dataset", help="Path to dataset directory")
    parser.add_argument("--output_path", type=str, default="output.csv", help="Path to output CSV")
    args = parser.parse_args()
    
    run_pipeline(dataset_dir=args.dataset_dir, output_csv_path=args.output_path)

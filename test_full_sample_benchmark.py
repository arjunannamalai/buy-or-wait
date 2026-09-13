"""
Benchmark script testing the complete financial agent on all 25 ground-truth samples in dataset/sample_requests.csv.
"""

import pandas as pd
import numpy as np
from code.data_loader import DataLoader
from code.forecast_engine import ForecastEngine
from code.planner import Planner
from code.explainer import DecisionExplainer

def run_benchmark():
    dl = DataLoader().load_all()
    engine = ForecastEngine(dl)
    planner = Planner(dl, engine)
    explainer = DecisionExplainer(dl)
    
    sample_df = dl.sample_requests_df
    total = len(sample_df)
    
    correct_status = 0
    correct_method = 0
    correct_plan = 0
    correct_spending = 0
    correct_earliest = 0
    
    results = []

    for idx, row in sample_df.iterrows():
        req_id = row['request_id']
        pred = planner.evaluate_request(row)
        pred_expl = explainer.generate_explanation(row, pred)
        pred['decision_explanation'] = pred_expl
        
        act_status = row['affordability_status']
        act_method = row['recommended_payment_method']
        act_plan = row['payment_plan']
        act_spending = row['spending_changes_needed']
        act_earliest = row['earliest_date_for_full_payment']
        if pd.isna(act_earliest):
            act_earliest = ''

        match_s = (pred['affordability_status'] == act_status)
        match_m = (pred['recommended_payment_method'] == act_method)
        match_p = (pred['payment_plan'] == act_plan)
        match_sp = (pred['spending_changes_needed'] == act_spending)
        match_e = (str(pred['earliest_date_for_full_payment']) == str(act_earliest))

        if match_s: correct_status += 1
        if match_m: correct_method += 1
        if match_p: correct_plan += 1
        if match_sp: correct_spending += 1
        if match_e: correct_earliest += 1
        
        results.append({
            'request_id': req_id,
            'match_status': match_s,
            'match_method': match_m,
            'match_plan': match_p,
            'pred_status': pred['affordability_status'],
            'act_status': act_status,
            'pred_method': pred['recommended_payment_method'],
            'act_method': act_method,
            'pred_plan': pred['payment_plan'],
            'act_plan': act_plan,
            'pred_safe': pred['amount_safe_to_pay'],
            'act_safe': row['amount_safe_to_pay'],
            'pred_ear': pred['earliest_date_for_full_payment'],
            'act_ear': act_earliest,
            'pred_expl': pred_expl,
            'act_expl': row['decision_explanation']
        })

    print("========================================================")
    print(f"BENCHMARK RESULTS ON {total} GROUND-TRUTH SAMPLES:")
    print("========================================================")
    print(f"Affordability Status Accuracy : {correct_status}/{total} ({correct_status/total*100:.1f}%)")
    print(f"Recommended Method Accuracy   : {correct_method}/{total} ({correct_method/total*100:.1f}%)")
    print(f"Payment Plan Accuracy         : {correct_plan}/{total} ({correct_plan/total*100:.1f}%)")
    print(f"Spending Changes Accuracy     : {correct_spending}/{total} ({correct_spending/total*100:.1f}%)")
    print(f"Earliest Date Accuracy        : {correct_earliest}/{total} ({correct_earliest/total*100:.1f}%)")
    print("========================================================")

    res_df = pd.DataFrame(results)
    mismatches = res_df[~(res_df['match_status'] & res_df['match_method'])]
    if len(mismatches) > 0:
        print("\nMismatches in Status/Method:")
        for idx, m in mismatches.iterrows():
            print(f"  {m['request_id']}: pred=({m['pred_status']}, {m['pred_method']}) vs act=({m['act_status']}, {m['act_method']})")
            print(f"     Safe: pred={m['pred_safe']:.2f}, act={m['act_safe']:.2f} | Ear: pred={m['pred_ear']}, act={m['act_ear']}")
            print(f"     Plan: pred={m['pred_plan']} vs act={m['act_plan']}")
    else:
        print("\nALL 25 STATUS & METHOD PREDICTIONS MATCH GROUND TRUTH PERFECTLY!")

if __name__ == '__main__':
    run_benchmark()

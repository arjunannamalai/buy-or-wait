import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from code.data_loader import DataLoader

dl = DataLoader().load_all()

def format_date_str(d):
    # e.g. 2025-08-08 -> 8 August 2025
    dt = datetime.strptime(d, '%Y-%m-%d')
    month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    return f"{dt.day} {month_names[dt.month]} {dt.year}"

def format_amount(amt):
    # If integer, no decimals, else 2 decimals
    if round(amt, 2) == round(amt, 0):
        return f"{int(round(amt)):,}"
    else:
        return f"{amt:,.2f}"

print("Pipeline tester initialized.")

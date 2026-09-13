"""
Pre-extracted and verified OCR amounts for the 16 financial events linked to images in dataset/media/images/.
Extracted using Apple Vision Framework VNRecognizeTextRequest on macOS.
"""

OCR_EVENT_AMOUNTS = {
    'event_253': 4365000.0,       # image_01: IDR 4,365,000 (Net salary Aug-2019)
    'event_1442': 100000.0,       # image_02: INR 100,000 (Outstanding rent balance)
    'event_1545': 41272.0,        # image_03: INR 41,272.0 (Bulk groceries and pantry purchase)
    'event_1700': 2854.0,         # image_04: INR 2,854.0 (Delivered grocery order)
    'event_1786': 704.05,         # image_05: INR 704.05 (Outstanding telecom bill)
    'event_3051': 1995.0,         # image_06: INR 1,995.0 (Grocery tax invoice)
    'event_3231': 8528.0,         # image_07: INR 8,528.0 (Restaurant tax invoice)
    'event_4535': 15339.0,        # image_08: INR 15,339.0 (Property maintenance invoice)
    'event_5170': 723.0,          # image_09: INR 723.0 (Water bill due)
    'event_6033': 79679.26,       # image_10: INR 79,679.26 (Large grocery tax invoice)
    'event_6859': 3650.0,         # image_11: INR 3,650.0 (Hospital bill payable)
    'event_7307': 33.50,          # image_12: USD 33.50 (Taxi fare)
    'event_7941': 2298.0,         # image_13: INR 2,298.0 (Tote bag order)
    'event_9421': 4543.0,         # image_14: INR 4,543.0 (Pharmacy purchase)
    'event_9806': 9968.0,         # image_15: INR 9,968.0 (Airline ticket purchase)
    'event_10521': 393.22         # image_16: INR 393.22 (EV charging wallet payment)
}

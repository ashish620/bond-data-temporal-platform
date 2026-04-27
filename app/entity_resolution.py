

import re
from override import log_override
from rapidfuzz import process
import pandas as pd

df = pd.read_csv("data/sample_instruments.csv")
def normalize_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9 ]', '', text)
    return text.strip()

def detect_issuer(query, issuers):
    query = query.lower()

    for issuer in issuers:
        if issuer.lower() in query:
            return issuer

    return None

def detect_tenor(query):
    query = query.lower()

    # Match 4-digit year
    year_match = re.search(r'\b(20\d{2})\b', query)
    if year_match:
        return year_match.group(1)

    # Match tenor like 5Y, 10Y
    tenor_match = re.search(r'\b(\d{1,2})\s*(y|year)\b', query)
    if tenor_match:
        return tenor_match.group(1) + "Y"

    return None

def detect_type(query, types):
    query = query.lower()

    for t in types:
        if t.lower() in query:
            return t

    return None

def extract_features(query, df):

    issuers = df['issuer'].dropna().unique()
    types = df['type'].dropna().unique()

    features = {
        "issuer": detect_issuer(query, issuers),
        "tenor": detect_tenor(query),
        "type": detect_type(query, types)
    }

    return features

def filter_candidates(df, features):
    if features is None:
        return df.copy()
    
    filtered = df.copy()

    if features["issuer"]:
        filtered = filtered[filtered["issuer"] == features["issuer"]]

    if features["tenor"]:
        filtered = filtered[filtered["tenor"] == features["tenor"]]

    if features["type"]:
        filtered = filtered[filtered["type"] == features["type"]]

    return filtered




def resolve_entity(query):

    features = extract_features(query,df)
    candidates = filter_candidates(df, features)

    if len(candidates) == 0:
        candidates = df

    names = candidates['name'].tolist()

    matches = process.extract(query, names, limit=3)

    results = []

    for match in matches:
        name, score, idx = match
        row = candidates.iloc[idx]

        results.append({
            "matched_name": name,
            "isin": row['isin'],
            "confidence": score
        })

    return {
        "query": query,
        "features": features,
        "results": results
    }
if __name__ == "__main__":
    print("running entity resolution")
    result = resolve_entity("apple bond 2030")
    print(result)

    suggested_isin = result["results"][0]["isin"]
    corrected_isin = "US0378331005" #user override

    override_log = log_override(suggested_isin,corrected_isin, "ashish")

    print(override_log)
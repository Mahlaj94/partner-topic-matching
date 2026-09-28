import pandas as pd

# Load the raw matrix
df = pd.read_csv("matrix-genai-sc-k30.csv")

# Map labels to numeric scores
LABEL_TO_SCORE = {
    "Yes": 3,
    "Weak": 1,
    "No": 0
}

df["score"] = df["label"].map(LABEL_TO_SCORE).fillna(0)

# Pivot to Partner × Supply Chain
matrix = df.pivot_table(
    index="partner_id",
    columns="topic_id",
    values="score",
    aggfunc="max",   # keep strongest contribution
    fill_value=0
)

# Save outputs
matrix.to_csv("matrix-genai-sc-k30-pivot.csv")

print("✅ Pivoted matrix written to matrix-genai-sc-k30-pivot.csv")

import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler, LabelEncoder

# === 1. Load the CSV file ===
csv_path = "/app/CICIoT2023/UploadingAttack/csv/BenignTraffic.csv"
output_dir="/app/output"
df = pd.read_csv(csv_path)

# === 2. Display available columns and preview ===
print("Available columns:", df.columns.tolist())
print("\nFirst few rows:")
print(df.head())

# === 3. Clean the data: remove missing values ===
df = df.dropna()

# === 4. Normalize the 'Tot size' column ===
if 'Tot size' in df.columns:
    scaler = MinMaxScaler()
    df['Tot_size_normalized'] = scaler.fit_transform(df[['Tot size']])
else:
    print("Column 'Tot size' not found, normalization skipped.")

# === 5. Encode the 'Protocol Type' column ===
if 'Protocol Type' in df.columns:
    encoder = LabelEncoder()
    df['Protocol_Type_encoded'] = encoder.fit_transform(df['Protocol Type'])
else:
    print("Column 'Protocol Type' not found, encoding skipped.")

# === 6. Plot histogram of 'Tot size' ===
if 'Tot size' in df.columns:
    plt.figure(figsize=(10, 5))
    plt.hist(df['Tot size'], bins=50, color='skyblue', edgecolor='black')
    plt.title("Histogram of Total Flow Size (Tot size)")
    plt.xlabel("Tot size")
    plt.ylabel("Number of flows")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/histogram_tot_size.png")
    plt.show()

# === 7. Plot bar chart of protocol types ===
if 'Protocol Type' in df.columns:
    plt.figure(figsize=(10, 5))
    df['Protocol Type'].value_counts().plot(kind='bar', color='orange')
    plt.title("Number of Flows per Protocol Type")
    plt.xlabel("Protocol type")
    plt.ylabel("Number of flows")
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(f"{output_dir}/barplot_protocol_type.png")
    plt.show()

# === 8. Save the modified DataFrame ===
df.to_csv("csv_analysis_modified.csv", index=False)
print("\Analysis completed successfully. Modified file saved as: csv_analysis_modified.csv")

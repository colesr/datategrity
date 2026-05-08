import json
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


def load_dataset(path: str) -> pd.DataFrame:
    if path.lower().endswith(".csv"):
        return pd.read_csv(path)
    if path.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(path)
    raise ValueError("Unsupported dataset format")


def get_dataset_preview(df: pd.DataFrame, max_rows: int = 10) -> Dict:
    """Generate a preview of the dataset for display"""
    if df is None or df.empty:
        return {"error": "DataFrame is empty"}
    
    return {
        "rows": len(df),
        "columns": len(df.columns),
        "column_names": df.columns.tolist(),
        "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "preview": df.head(max_rows).to_dict(orient="records"),
        "memory_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
    }


def analyze_data_quality(df: pd.DataFrame, columns: Optional[List[str]] = None) -> Dict:
    if df is None or df.empty:
        return {"error": "DataFrame is empty"}

    if columns:
        columns = [col for col in columns if col in df.columns]
    else:
        columns = df.columns.tolist()

    analysis = {
        "dataset_info": {
            "rows": len(df),
            "columns": len(df.columns),
            "memory_usage_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
        },
        "column_analysis": {},
        "missing_values": {},
        "duplicate_rows": int(df.duplicated().sum()),
    }

    for col in columns:
        col_data = df[col]
        stats = {
            "dtype": str(col_data.dtype),
            "non_null": int(col_data.count()),
            "null_count": int(col_data.isna().sum()),
            "null_percentage": round(col_data.isna().mean() * 100, 2),
            "unique_values": int(col_data.nunique(dropna=True)),
        }

        if pd.api.types.is_numeric_dtype(col_data):
            stats.update({
                "min": float(col_data.min() if not col_data.dropna().empty else np.nan),
                "max": float(col_data.max() if not col_data.dropna().empty else np.nan),
                "mean": round(float(col_data.mean() if not col_data.dropna().empty else np.nan), 2),
                "std": round(float(col_data.std() if not col_data.dropna().empty else np.nan), 2),
                "skewness": round(float(col_data.skew() if not col_data.dropna().empty else np.nan), 2),
            })
        elif pd.api.types.is_string_dtype(col_data) or pd.api.types.is_object_dtype(col_data):
            stats["sample_values"] = col_data.dropna().astype(str).head(5).tolist()

        analysis["column_analysis"][col] = stats

    analysis["missing_values"]["total_missing"] = int(df.isna().sum().sum())
    analysis["missing_values"]["missing_by_column"] = {k: int(v) for k, v in df.isna().sum().to_dict().items()}

    return analysis


def detect_anomalies(df: pd.DataFrame, column: str, method: str = "zscore") -> Dict:
    if df is None or df.empty:
        return {"error": "No data loaded"}

    if column not in df.columns:
        return {"error": "Invalid column selected"}

    if not pd.api.types.is_numeric_dtype(df[column]):
        return {"error": "Column must be numeric"}

    data = df[column].dropna()
    if data.empty:
        return {"error": "No valid data in column"}

    if method == "zscore":
        z_scores = np.abs((data - data.mean()) / data.std())
        threshold = 3
        anomalies = data[z_scores > threshold]
    elif method == "iqr":
        q1 = data.quantile(0.25)
        q3 = data.quantile(0.75)
        iqr = q3 - q1
        anomalies = data[(data < q1 - 1.5 * iqr) | (data > q3 + 1.5 * iqr)]
    else:
        return {"error": "Invalid method"}

    return {
        "method": method,
        "total_anomalies": int(len(anomalies)),
        "anomaly_percentage": round(float(len(anomalies) / len(data)) * 100, 2),
        "anomaly_indices": anomalies.index.tolist()[:10],
        "anomaly_values": [float(x) for x in anomalies.values[:10]],
    }


def generate_data_quality_report(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "# Error: No data loaded"

    analysis = analyze_data_quality(df)
    report = [
        "# Data Quality Report",
        "",
        "## Dataset Overview",
        f"- **Total Rows**: {analysis['dataset_info']['rows']}",
        f"- **Total Columns**: {analysis['dataset_info']['columns']}",
        f"- **Memory Usage**: {analysis['dataset_info']['memory_usage_mb']} MB",
        f"- **Duplicate Rows**: {analysis['duplicate_rows']}",
        "",
        "## Missing Values Summary",
        f"- **Total Missing Values**: {analysis['missing_values']['total_missing']}",
        "- **Missing by Column**:",
        "```json",
        json.dumps(analysis['missing_values']['missing_by_column'], indent=2),
        "```",
        "",
        "## Column Analysis",
    ]

    for col, stats in analysis['column_analysis'].items():
        report.append(f"### {col}")
        report.append(f"- **Data Type**: {stats['dtype']}")
        report.append(f"- **Non-null Values**: {stats['non_null']} ({100 - stats['null_percentage']}%)")
        report.append(f"- **Null Values**: {stats['null_count']} ({stats['null_percentage']}%)")
        report.append(f"- **Unique Values**: {stats['unique_values']}")
        if "min" in stats:
            report.append(
                f"- **Min**: {stats['min']}, **Max**: {stats['max']}, **Mean**: {stats['mean']}, **Std**: {stats['std']}"
            )
        report.append("")

    return "\n".join(report)


def validate_data_integrity(df: pd.DataFrame, rules: str) -> List[Dict]:
    if df is None or df.empty:
        return [{"rule": "No data", "passed": False, "error": "Upload data first"}]

    if not rules or not rules.strip():
        return [{"rule": "No rules provided", "passed": True, "notes": "Please enter validation rules in format: column:type:param"}]

    results = []
    for rule in [r.strip() for r in rules.split(",") if r.strip()]:
        try:
            if ":" in rule:
                parts = rule.split(":")
                if len(parts) == 3:
                    column, rule_type, parameter = parts
                    if column not in df.columns:
                        results.append({"rule": f"{column} (column not found)", "passed": False, "error": f"Column '{column}' not in dataset"})
                        continue

                    if rule_type == "null":
                        invalid = int(df[column].isna().sum())
                        total = len(df)
                        results.append({
                            "rule": f"{column} must not be null",
                            "passed": invalid == 0,
                            "violations": invalid,
                            "total_rows": total,
                            "compliance_rate": round((total - invalid) / total * 100, 2) if total else 0,
                        })
                    elif rule_type == "unique":
                        duplicates = int(df.duplicated(subset=[column]).sum())
                        total = len(df)
                        results.append({
                            "rule": f"{column} must be unique",
                            "passed": duplicates == 0,
                            "violations": duplicates,
                            "total_rows": total,
                            "compliance_rate": round((total - duplicates) / total * 100, 2) if total else 0,
                        })
                    elif rule_type == "range":
                        min_val, max_val = map(float, parameter.split(","))
                        violations = int(((df[column] < min_val) | (df[column] > max_val)).sum())
                        total = len(df)
                        results.append({
                            "rule": f"{column} must be in range [{min_val}, {max_val}]",
                            "passed": violations == 0,
                            "violations": violations,
                            "total_rows": total,
                            "compliance_rate": round((total - violations) / total * 100, 2) if total else 0,
                        })
                    else:
                        results.append({"rule": rule, "passed": False, "error": f"Unknown rule type: {rule_type}"})
                else:
                    results.append({"rule": rule, "passed": False, "error": "Invalid rule format (expected: column:type:param)"})
            else:
                results.append({"rule": rule, "passed": False, "error": "Invalid rule format (expected: column:type:param)"})
        except Exception as exc:
            results.append({"rule": rule, "passed": False, "error": str(exc)})

    return results


def clean_data(df: pd.DataFrame, operations: str) -> Dict:
    if df is None or df.empty:
        return {"error": "No data loaded"}

    if not operations or not operations.strip():
        return {"preview": df.head(10).to_dict(orient="records"), "actions": []}

    cleaned_df = df.copy()
    actions = []
    for operation in [op.strip() for op in operations.split(",") if op.strip()]:
        try:
            if ":" in operation:
                column, op_type = operation.split(":", 1)
                if column not in cleaned_df.columns:
                    actions.append({"column": column, "action": "column_not_found"})
                    continue

                if op_type == "drop_null":
                    before = len(cleaned_df)
                    cleaned_df = cleaned_df.dropna(subset=[column])
                    actions.append({"column": column, "action": f"dropped_null_rows {before - len(cleaned_df)}"})
                elif op_type == "fill_mean":
                    if pd.api.types.is_numeric_dtype(cleaned_df[column]):
                        mean_val = cleaned_df[column].mean()
                        cleaned_df[column] = cleaned_df[column].fillna(mean_val)
                        actions.append({"column": column, "action": f"filled_nulls_with_mean_{round(mean_val, 2)}"})
                    else:
                        actions.append({"column": column, "action": "cannot_fill_mean_non_numeric"})
                elif op_type == "fill_median":
                    if pd.api.types.is_numeric_dtype(cleaned_df[column]):
                        median_val = cleaned_df[column].median()
                        cleaned_df[column] = cleaned_df[column].fillna(median_val)
                        actions.append({"column": column, "action": f"filled_nulls_with_median_{round(median_val, 2)}"})
                    else:
                        actions.append({"column": column, "action": "cannot_fill_median_non_numeric"})
                elif op_type == "lowercase":
                    cleaned_df[column] = cleaned_df[column].astype(str).str.lower()
                    actions.append({"column": column, "action": "lowercased_text"})
                elif op_type == "trim":
                    cleaned_df[column] = cleaned_df[column].astype(str).str.strip()
                    actions.append({"column": column, "action": "trimmed_whitespace"})
                else:
                    actions.append({"column": column, "action": f"unknown_operation_{op_type}"})
            else:
                actions.append({"operation": operation, "result": "invalid_format"})
        except Exception as exc:
            actions.append({"operation": operation, "result": f"error_{str(exc)}"})

    return {
        "actions": actions,
        "preview": cleaned_df.head(10).to_dict(orient="records"),
        "rows": len(cleaned_df),
        "columns": len(cleaned_df.columns),
    }

import gradio as gr
import pandas as pd
import numpy as np
from huggingface_hub import InferenceClient
import io
import json
from datetime import datetime
import re

def analyze_data_quality(df, columns=None):
    """Comprehensive data quality analysis"""
    if df is None or df.empty:
        return {"error": "DataFrame is empty"}
    
    if columns is None:
        columns = df.columns.tolist()
    
    analysis = {
        "dataset_info": {
            "rows": len(df),
            "columns": len(df.columns),
            "memory_usage": round(df.memory_usage(deep=True).sum() / 1024**2, 2),  # MB
        },
        "column_analysis": {},
        "missing_values": {},
        "duplicate_rows": int(df.duplicated().sum())
    }
    
    for col in columns:
        col_data = df[col]
        analysis["column_analysis"][col] = {
            "dtype": str(col_data.dtype),
            "non_null": int(col_data.count()),
            "null_count": int(col_data.isna().sum()),
            "null_percentage": round(col_data.isna().mean() * 100, 2),
            "unique_values": int(col_data.nunique()),
        }
        
        if pd.api.types.is_numeric_dtype(col_data):
            analysis["column_analysis"][col].update({
                "min": float(col_data.min()),
                "max": float(col_data.max()),
                "mean": round(float(col_data.mean()), 2),
                "std": round(float(col_data.std()), 2),
                "skewness": round(float(col_data.skew()), 2)
            })
        elif pd.api.types.is_string_dtype(col_data):
            analysis["column_analysis"][col]["sample_values"] = col_data.dropna().head(3).tolist()
    
    # Missing values matrix
    analysis["missing_values"]["total_missing"] = int(df.isna().sum().sum())
    analysis["missing_values"]["missing_by_column"] = {k: int(v) for k, v in df.isna().sum().to_dict().items()}
    
    return analysis

def detect_anomalies(df, column, method="zscore"):
    """Detect anomalies in numerical column"""
    if df is None or df.empty:
        return {"error": "No data loaded"}
    
    if column is None or column not in df.columns:
        return {"error": "Invalid column selected"}
    
    if not pd.api.types.is_numeric_dtype(df[column]):
        return {"error": "Column must be numeric"}
    
    data = df[column].dropna()
    
    if len(data) == 0:
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
        "anomaly_percentage": round(float(len(anomalies) / len(data)) * 100, 2) if len(data) > 0 else 0,
        "anomaly_indices": anomalies.index.tolist()[:10],  # First 10 indices
        "anomaly_values": [float(x) for x in anomalies.values[:10]]  # First 10 values
    }

def generate_data_quality_report(df):
    """Generate comprehensive data quality report"""
    if df is None or df.empty:
        return "# Error: No data loaded"
    
    analysis = analyze_data_quality(df)
    
    report = f"""# Data Quality Report

## Dataset Overview
- **Total Rows**: {analysis['dataset_info']['rows']}
- **Total Columns**: {analysis['dataset_info']['columns']}
- **Memory Usage**: {analysis['dataset_info']['memory_usage']:.2f} MB
- **Duplicate Rows**: {analysis['duplicate_rows']}

## Missing Values Summary
- **Total Missing Values**: {analysis['missing_values']['total_missing']}
- **Missing by Column**: {json.dumps(analysis['missing_values']['missing_by_column'], indent=2)}

## Column Analysis

"""
    
    for col, stats in analysis['column_analysis'].items():
        report += f"""
### {col}
- **Data Type**: {stats['dtype']}
- **Non-null Values**: {stats['non_null']} ({100 - stats['null_percentage']}%)
- **Null Values**: {stats['null_count']} ({stats['null_percentage']}%)
- **Unique Values**: {stats['unique_values']}
"""
        if 'min' in stats:
            report += f"- **Min**: {stats['min']}, **Max**: {stats['max']}, **Mean**: {stats['mean']}, **Std**: {stats['std']}\n"
    
    return report

def chat_with_data(df, message, history, hf_token):
    """AI-powered data analysis assistant"""
    if df is None or df.empty:
        yield "Please upload data first."
        return
    
    try:
        if not hf_token or hf_token.strip() == "":
            yield "⚠️ Please provide a valid Hugging Face token in the Settings tab. Get one from https://huggingface.co/settings/tokens"
            return
        
        client = InferenceClient(token=hf_token.strip(), model="openai/gpt-oss-20b")
        
        # Create context from data
        data_context = f"""
Dataset Information:
- Rows: {len(df)}
- Columns: {list(df.columns)}
- Data types: {df.dtypes.to_dict()}

Sample Data (first 5 rows):
{df.head().to_string()}
"""
        
        # Build conversation context
        messages = [
            {"role": "system", "content": f"""You are an expert data analyst assistant. 
            Use the following dataset information to answer questions about the data:
            {data_context}
            
            When asked about data quality, anomalies, or statistics, use the dataset context provided.
            Be concise and focus on actionable insights."""},
            *history,
            {"role": "user", "content": message}
        ]
        
        response = ""
        for message_response in client.chat_completion(
            messages,
            max_tokens=1024,
            stream=True,
            temperature=0.7,
            top_p=0.95,
        ):
            choices = message_response.choices
            if len(choices) and choices[0].delta.content:
                response += choices[0].delta.content
                yield response
                
    except Exception as e:
        yield f"❌ Error: {str(e)}\n\n💡 Make sure your Hugging Face token is valid and has the necessary permissions."

def validate_data_integrity(df, rules):
    """Validate data against business rules"""
    if df is None or df.empty:
        return pd.DataFrame([{"rule": "No data", "passed": False, "error": "Upload data first"}])
    
    if not rules or not rules.strip():
        return pd.DataFrame([{"rule": "No rules provided", "passed": True, "notes": "Please enter validation rules in format: column:type:param"}])
    
    results = []
    
    try:
        for rule in [r.strip() for r in rules.split(',') if r.strip()]:
            try:
                # Parse rule (simple format: "column:rule_type:parameter")
                if ':' in rule:
                    parts = rule.split(':')
                    if len(parts) == 3:
                        column, rule_type, parameter = parts
                        
                        if column not in df.columns:
                            results.append({
                                "rule": f"{column} (column not found)",
                                "passed": False,
                                "error": f"Column '{column}' not in dataset"
                            })
                            continue
                        
                        if rule_type == "null":
                            invalid = int(df[column].isna().sum())
                            total = len(df)
                            results.append({
                                "rule": f"{column} must not be null",
                                "passed": invalid == 0,
                                "violations": invalid,
                                "total_rows": total,
                                "compliance_rate": round((total - invalid) / total * 100, 2) if total > 0 else 0
                            })
                        elif rule_type == "unique":
                            duplicates = int(df.duplicated(subset=[column]).sum())
                            results.append({
                                "rule": f"{column} must be unique",
                                "passed": duplicates == 0,
                                "violations": duplicates,
                                "total_rows": len(df),
                                "compliance_rate": round((len(df) - duplicates) / len(df) * 100, 2) if len(df) > 0 else 0
                            })
                        elif rule_type == "range":
                            min_val, max_val = map(float, parameter.split(','))
                            violations = int(((df[column] < min_val) | (df[column] > max_val)).sum())
                            results.append({
                                "rule": f"{column} must be in range [{min_val}, {max_val}]",
                                "passed": violations == 0,
                                "violations": violations,
                                "total_rows": len(df),
                                "compliance_rate": round((len(df) - violations) / len(df) * 100, 2) if len(df) > 0 else 0
                            })
                        else:
                            results.append({
                                "rule": rule,
                                "passed": False,
                                "error": f"Unknown rule type: {rule_type}"
                            })
                    else:
                        results.append({
                            "rule": rule,
                            "passed": False,
                            "error": "Invalid rule format (expected: column:type:param)"
                        })
                else:
                    results.append({
                        "rule": rule,
                        "passed": False,
                        "error": "Invalid rule format (expected: column:type:param)"
                    })
            except Exception as e:
                results.append({
                    "rule": rule,
                    "passed": False,
                    "error": str(e)
                })
    except Exception as e:
        results.append({
            "rule": "Batch validation",
            "passed": False,
            "error": f"Validation failed: {str(e)}"
        })
    
    return pd.DataFrame(results)

def clean_data(df, operations):
    """Apply data cleaning operations"""
    if df is None or df.empty:
        return pd.DataFrame([["No data", "Please upload data first"]], columns=["Column", "Action"])
    
    if not operations or not operations.strip():
        return df.head(10)
    
    cleaned_df = df.copy()
    results = []
    
    try:
        for operation in [op.strip() for op in operations.split(',') if op.strip()]:
            try:
                if ':' in operation:
                    parts = operation.split(':')
                    if len(parts) == 2:
                        column, op_type = parts
                        
                        if column not in cleaned_df.columns:
                            results.append([column, f"Column not found"])
                            continue
                        
                        original_count = len(cleaned_df)
                        
                        if op_type == "drop_null":
                            cleaned_df = cleaned_df.dropna(subset=[column])
                            results.append([column, f"Dropped {original_count - len(cleaned_df)} null rows"])
                        elif op_type == "fill_mean":
                            if pd.api.types.is_numeric_dtype(cleaned_df[column]):
                                mean_val = cleaned_df[column].mean()
                                cleaned_df[column] = cleaned_df[column].fillna(mean_val)
                                results.append([column, f"Filled nulls with mean: {round(mean_val, 2)}"])
                            else:
                                results.append([column, "Cannot fill mean - column not numeric"])
                        elif op_type == "fill_median":
                            if pd.api.types.is_numeric_dtype(cleaned_df[column]):
                                median_val = cleaned_df[column].median()
                                cleaned_df[column] = cleaned_df[column].fillna(median_val)
                                results.append([column, f"Filled nulls with median: {round(median_val, 2)}"])
                            else:
                                results.append([column, "Cannot fill median - column not numeric"])
                        elif op_type == "lowercase":
                            cleaned_df[column] = cleaned_df[column].astype(str).str.lower()
                            results.append([column, "Converted to lowercase"])
                        elif op_type == "trim":
                            cleaned_df[column] = cleaned_df[column].astype(str).str.strip()
                            results.append([column, "Trimmed whitespace"])
                        else:
                            results.append([column, f"Unknown operation: {op_type}"])
                    else:
                        results.append([operation, "Invalid operation format"])
            except Exception as e:
                results.append([operation, f"Error: {str(e)}"])
    except Exception as e:
        results.append(["Batch cleaning", f"Failed: {str(e)}"])
    
    # Return cleaned preview if no specific results, otherwise return results
    if not results:
        return cleaned_df.head(10)
    return pd.DataFrame(results, columns=["Column", "Action"]).head(20)

def get_completion_suggestions(text, columns, rule_types=["null", "unique", "range"]):
    """Generate real-time suggestions for business rules"""
    if not text or not columns:
        return []
    
    # Parse the current text to get partial rule
    parts = text.split(':')
    current_part = parts[-1].strip() if parts else ""
    
    suggestions = []
    
    # If we're at the beginning of a rule (before first colon)
    if len(parts) == 1 and current_part:
        # Suggest columns that start with the current text
        matching_columns = [col for col in columns if col.lower().startswith(current_part.lower())]
        suggestions = [f"{col}:" for col in matching_columns[:5]]
    
    # If we have column but no rule type (after first colon, before second)
    elif len(parts) == 2 and current_part:
        # Suggest rule types that start with current text
        matching_rules = [rule for rule in rule_types if rule.lower().startswith(current_part.lower())]
        if "range" in matching_rules:
            suggestions = [f"{rule}:" for rule in matching_rules[:4]]
            suggestions.append("range:0,1000")  # Special case for range
        else:
            suggestions = [f"{rule}:" for rule in matching_rules[:4]]
    
    # If we have column and rule type but no parameter (after second colon)
    elif len(parts) >= 3 and current_part and parts[-2].strip() == "range":
        # For range rules, suggest common value patterns
        if current_part in ["", "0", "1"]:
            suggestions = ["0,100", "0,1000", "1,100", "-100,100"]
        else:
            # Try to parse current input and suggest completion
            try:
                current_vals = current_part.split(',')
                if len(current_vals) == 1:
                    suggestions = [f"{current_vals[0]},100", f"{current_vals[0]},1000"]
                elif len(current_vals) == 2:
                    suggestions = [f"{current_vals[0]},{current_vals[1]}"]
            except:
                pass
    
    return suggestions[:5]  # Return up to 5 suggestions

def create_demo():
    """Create the main Gradio application"""
    with gr.Blocks() as demo:
        gr.Markdown("# 📊 Data Integrity & Quality Analyst Workbench")
        gr.Markdown("An all-in-one solution for data quality analysis, validation, and AI-powered insights")
        
        # Store data globally
        data_state = gr.State(value=None)
        
        # Hugging Face token input
        with gr.Accordion("⚙️ Settings", open=False):
            gr.Markdown("### Hugging Face Token Configuration")
            hf_token_input = gr.Textbox(
                label="Hugging Face Token", 
                type="password",
                placeholder="hf_...",
                info="Get your token from https://huggingface.co/settings/tokens"
            )
            gr.Markdown("*This token is used for AI-powered data analysis features. It's stored locally in your session.*")
        
        with gr.Tabs():
            # Upload & Explore Tab
            with gr.TabItem("📂 Upload & Explore"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Data Upload")
                        file_input = gr.File(
                            label="Upload CSV/Excel (.csv, .xlsx, .xls)", 
                            file_types=[".csv", ".xlsx", ".xls"]
                        )
                        gr.Markdown("✅ Supported formats: CSV, Excel (.xlsx, .xls)")
                        
                        sample_size = gr.Slider(
                            minimum=10, 
                            maximum=1000, 
                            value=100, 
                            step=10, 
                            label="Sample Size",
                            info="Number of rows to display initially"
                        )
                        load_btn = gr.Button("🚀 Load Data", variant="primary")
                        
                        gr.Markdown("### Quick Actions")
                        explore_btn = gr.Button("📊 Quick Explore", variant="secondary")
                        quality_btn = gr.Button("🔍 Quality Check", variant="secondary")
                        
                    with gr.Column(scale=2):
                        data_info = gr.JSON(label="Dataset Information")
                        sample_data = gr.Dataframe(
                            label="Sample Data", 
                            interactive=False
                        )
                        
            # Quality Analysis Tab
            with gr.TabItem("🔍 Quality Analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Quality Metrics")
                        quality_columns = gr.Dropdown(
                            label="Select Columns", 
                            multiselect=True,
                            info="Select columns to analyze (leave empty for all columns)"
                        )
                        analyze_quality_btn = gr.Button("🎯 Analyze Quality", variant="primary")
                        
                        gr.Markdown("### Anomaly Detection")
                        anomaly_column = gr.Dropdown(
                            label="Select Column for Anomaly Detection",
                            info="Select a numeric column to detect anomalies"
                        )
                        anomaly_method = gr.Radio(
                            ["zscore", "iqr"], 
                            value="zscore", 
                            label="Detection Method",
                            info="zscore: Standard deviation method | iqr: Interquartile range method"
                        )
                        detect_anomalies_btn = gr.Button("⚠️ Detect Anomalies")
                        
                    with gr.Column(scale=2):
                        quality_report = gr.JSON(label="Quality Analysis")
                        anomaly_results = gr.JSON(label="Anomaly Detection Results")
                        
            # AI Assistant Tab
            with gr.TabItem("🤖 AI Assistant"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Data Assistant")
                        ai_message = gr.Textbox(
                            label="Ask about your data", 
                            placeholder="e.g., 'What are the top 5 rows by value?' or 'Find anomalies in column X'",
                            info="Ask questions about your dataset using natural language"
                        )
                        ai_history = gr.List(
                            label="Chat History"
                        )
                        ai_btn = gr.Button("💬 Ask AI", variant="primary")
                        ai_clear_btn = gr.Button("🗑️ Clear Chat")
                        
                    with gr.Column(scale=2):
                        ai_response = gr.Textbox(
                            label="AI Response", 
                            lines=10
                        )
                        ai_insights = gr.Markdown(label="Insights")
                        
            # Validation & Cleaning Tab
            with gr.TabItem("✅ Validation & Cleaning"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Business Rules Validation")
                        gr.Markdown("💡 **Tip**: Type your rules with real-time suggestions. Format: `column:rule_type:param`")
                        
                        rules_input = gr.Textbox(
                            label="Rules (format: column:rule_type:param)", 
                            placeholder="id:unique, price:range:0,1000, email:null",
                            lines=8,
                            info="Enter validation rules separated by commas. Use tab for autocomplete suggestions."
                        )
                        
                        # Hidden component to store current column list for suggestions
                        columns_state = gr.State(value=[])
                        
                        # Create suggestion display
                        with gr.Accordion("✅ Suggestions", open=False) as suggestions_accordion:
                            with gr.Column() as suggestions_container:
                                suggestions_list = gr.Radio(
                                    [], 
                                    label="Select suggestion", 
                                    value=None,
                                    interactive=True
                                )
                        
                        validate_btn = gr.Button("✅ Validate Data", variant="primary")
                        
                        gr.Markdown("### Data Cleaning Operations")
                        cleaning_ops = gr.Textbox(
                            label="Cleaning Operations (format: column:operation)", 
                            placeholder="name:lowercase, price:fill_mean, description:trim",
                            lines=5,
                            info="Enter cleaning operations separated by commas. Format: column:operation"
                        )
                        clean_btn = gr.Button("🧹 Clean Data", variant="secondary")
                        download_clean_btn = gr.Button("💾 Download Cleaned Data", variant="secondary")
                        
                    with gr.Column(scale=2):
                        validation_results = gr.Dataframe(
                            label="Validation Results"
                        )
                        cleaning_preview = gr.Dataframe(
                            label="Cleaned Data Preview"
                        )
                        
            # Reporting Tab
            with gr.TabItem("📋 Reporting"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Generate Reports")
                        report_type = gr.Radio(
                            ["Quality Report", "Anomaly Summary", "Validation Summary"], 
                            label="Report Type",
                            info="Select the type of report to generate"
                        )
                        generate_report_btn = gr.Button("📄 Generate Report", variant="primary")
                        download_report_btn = gr.Button("📥 Download Report", variant="secondary")
                        
                    with gr.Column(scale=2):
                        report_output = gr.Markdown(label="Report")
                        report_json = gr.JSON(label="Report JSON")
        
        # Event Handlers - Updated with real-time suggestions
        def update_quality_columns(file):
            if file is None:
                return gr.update(choices=[])
            try:
                # Try to read the file
                if hasattr(file, 'name'):
                    if file.name.endswith('.csv'):
                        df = pd.read_csv(file.name)
                    else:
                        df = pd.read_excel(file.name)
                    return gr.update(choices=df.columns.tolist())
                else:
                    return gr.update(choices=[])
            except Exception as e:
                gr.Warning(f"Could not read file: {str(e)}")
                return gr.update(choices=[])
        
        def update_anomaly_column(file):
            if file is None:
                return gr.update(choices=[])
            try:
                if hasattr(file, 'name'):
                    if file.name.endswith('.csv'):
                        df = pd.read_csv(file.name)
                    else:
                        df = pd.read_excel(file.name)
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    return gr.update(choices=numeric_cols)
                else:
                    return gr.update(choices=[])
            except Exception as e:
                gr.Warning(f"Could not read file: {str(e)}")
                return gr.update(choices=[])
        
        def analyze_quality(df, columns):
            if df is None or df.empty:
                return {"error": "No data loaded. Please upload data first."}
            try:
                return analyze_data_quality(df, columns)
            except Exception as e:
                return {"error": f"Analysis failed: {str(e)}"}
        
        def detect_anomalies_handler(df, column, method):
            if df is None or df.empty:
                return {"error": "No data loaded. Please upload data first."}
            if column is None:
                return {"error": "Please select a column for anomaly detection."}
            try:
                return detect_anomalies(df, column, method)
            except Exception as e:
                return {"error": f"Anomaly detection failed: {str(e)}"}
        
        def chat_with_data_handler(message, history, hf_token):
            if data_state.value is None or data_state.value.empty:
                return "Please upload data first.", history
            
            response = ""
            full_history = history or []


            
            try:
                for partial_response in chat_with_data(data_state.value, message, history or [], hf_token):
                    response = partial_response
                    # Update history as we stream
                    current_history = full_history + [{"role": "user", "content": message}]
                    if partial_response and not partial_response.startswith("❌") and not partial_response.startswith("⚠️"):
                        current_history.append({"role": "assistant", "content": partial_response})
                    yield partial_response, current_history
            except Exception as e:
                error_response = f"❌ Error: {str(e)}"
                current_history = full_history + [{"role": "user", "content": message}]
                current_history.append({"role": "assistant", "content": error_response})
                yield error_response, current_history
        
        def validate_data_handler(df, rules):
            try:
                return validate_data_integrity(df, rules)
            except Exception as e:
                return pd.DataFrame([{"rule": "Error", "passed": False, "error": str(e)}])
        
        def clean_data_handler(df, operations):
            try:
                return clean_data(df, operations)
            except Exception as e:
                return pd.DataFrame([["Error", str(e)]], columns=["Column", "Action"])
        
        def generate_report(df, report_type):
            if df is None or df.empty:
                return "# Error: No data loaded", {"error": "No data"}
            
            try:
                if report_type == "Quality Report":
                    report_text = generate_data_quality_report(df)
                    analysis = analyze_data_quality(df)
                    return report_text, analysis
                elif report_type == "Anomaly Summary":
                    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
                    anomalies = {}
                    for col in numeric_cols[:5]:  # Limit to first 5 numeric columns
                        try:
                            anomalies[col] = detect_anomalies(df, col)
                        except:
                            continue
                    summary = f"# Anomaly Summary\n\nDetected anomalies in {len(anomalies)} numeric columns"
                    return summary, anomalies
                elif report_type == "Validation Summary":
                    return "# Validation Summary\n\nRun validation to see results", {"status": "Run validation first"}
            except Exception as e:
                return f"# Error: {str(e)}", {"error": str(e)}
        
        def load_data(file, sample_size):
            """Load data with comprehensive error handling"""
            if file is None:
                return None, {}, pd.DataFrame(), "No file uploaded"
            
            try:
                # Check if file has the expected attributes
                if not hasattr(file, 'name'):
                    return None, {"error": "Invalid file object"}, pd.DataFrame(), "Invalid file format"
                
                filename = file.name if hasattr(file, 'name') else str(file)
                
                # Read the file based on extension
                if filename.endswith('.csv'):
                    df = pd.read_csv(file.name)
                elif filename.endswith('.xlsx') or filename.endswith('.xls'):
                    df = pd.read_excel(file.name)
                else:
                    return None, {"error": "Unsupported file format. Please use CSV or Excel files."}, pd.DataFrame(), "Unsupported format"
                
                # Store full dataset
                data_state.value = df.copy()
                
                # Sample for display
                sample_size = int(sample_size)
                sample_df = df.head(sample_size)
                
                # Generate quick analysis
                quick_analysis = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "memory_mb": round(df.memory_usage(deep=True).sum() / 1024**2, 2),
                    "columns_list": df.columns.tolist(),
                    "data_types": df.dtypes.astype(str).value_counts().to_dict()
                }









                
                status = f"✅ Successfully loaded {len(df)} rows and {len(df.columns)} columns"


                
                return df, quick_analysis, sample_df, status
                
            except pd.errors.EmptyDataError:
                return None, {"error": "File is empty"}, pd.DataFrame(), "Empty file"
            except pd.errors.ParserError as e:
                return None, {"error": f"CSV parsing error: {str(e)}"}, pd.DataFrame(), "Parse error"
            except Exception as e:
                return None, {"error": f"Error loading file: {str(e)}"}, pd.DataFrame(), f"Error: {str(e)}"
        
        def update_columns_state(file):
            """Update the columns state when file is uploaded"""
            if file is None:
                return []
            try:
                if hasattr(file, 'name'):
                    if file.name.endswith('.csv'):
                        df = pd.read_csv(file.name)
                    else:
                        df = pd.read_excel(file.name)
                    return df.columns.tolist()
                else:
                    return []
            except Exception:
                return []
        
        def get_suggestions(text, columns):
            """Get completion suggestions for the rules input"""
            if not text or not columns:
                return [], False
            
            try:
                suggestions = get_completion_suggestions(text, columns)
                return suggestions, len(suggestions) > 0
            except Exception:
                return [], False
        
        def select_suggestion(suggestion, current_text):
            """Handle suggestion selection"""
            if not suggestion:
                return current_text
            
            # If suggestion is a rule type, append it to current text
            parts = current_text.split(':')
            if len(parts) >= 2:
                # Reconstruct with suggestion
                base = ':'.join(parts[:-1])
                if suggestion.endswith(':'):
                    return f"{base}:{suggestion[:-1]}:"
                else:
                    return f"{base}:{suggestion}"
            
            return current_text + (suggestion if not current_text.endswith(':') else suggestion[1:])
        
        def toggle_suggestions_accordion(has_suggestions):
            """Toggle the accordion visibility based on suggestions"""
            return gr.update(visible=has_suggestions)
        
        # Connect events with real-time suggestions
        file_input.change(
            update_quality_columns, 
            file_input, 
            quality_columns
        )
        
        file_input.change(
            update_anomaly_column, 
            file_input, 
            anomaly_column
        )
        
        file_input.change(
            update_columns_state,
            file_input,
            columns_state
        )
        
        # Update load button to show status
        load_state = gr.State(value="Ready")
        
        load_btn.click(
            load_data, 
            [file_input, sample_size], 
            [data_state, data_info, sample_data, load_state]
        ).then(
            lambda status: gr.Info(status) if "Error" not in status else None,
            load_state,
            None
        )
        
        explore_btn.click(
            lambda df: (df.describe().to_dict() if df is not None and not df.empty else {}),
            data_state,
            data_info
        )
        
        quality_btn.click(
            lambda df: analyze_data_quality(df) if df is not None and not df.empty else {"error": "No data loaded"},
            data_state,
            quality_report
        )
        
        analyze_quality_btn.click(
            analyze_quality,
            [data_state, quality_columns],
            quality_report
        )
        
        detect_anomalies_btn.click(
            detect_anomalies_handler,
            [data_state, anomaly_column, anomaly_method],
            anomaly_results
        )
        
        ai_btn.click(
            chat_with_data_handler,
            [ai_message, ai_history, hf_token_input],
            [ai_response, ai_history],
            api_visibility="public"
        )
        
        ai_clear_btn.click(
            lambda: ("", []),
            None,
            [ai_response, ai_history]
        )
        
        validate_btn.click(
            validate_data_handler,
            [data_state, rules_input],
            validation_results
        )
        
        clean_btn.click(
            clean_data_handler,
            [data_state, cleaning_ops],
            cleaning_preview
        )
        
        download_clean_btn.click(
            lambda df: df.to_csv(index=False) if df is not None and not df.empty else "",
            data_state,
            gr.File(label="Download Cleaned Data")
        )
        
        generate_report_btn.click(
            generate_report,
            [data_state, report_type],
            [report_output, report_json]
        )
        
        download_report_btn.click(
            lambda report: report,
            report_output,
            gr.File(label="Download Report")
        )
        
        # Real-time suggestions for rules input - using change event (Gradio 6 compatible)
        rules_input.change(
            get_suggestions,
            [rules_input, columns_state],
            [suggestions_list, gr.Checkbox(visible=False)]  # Use a dummy checkbox for the second output
        ).then(
            toggle_suggestions_accordion,
            gr.Checkbox(visible=False),
            suggestions_accordion
        )
        
        suggestions_list.change(
            select_suggestion,
            [suggestions_list, rules_input],
            rules_input
        )
    
    return demo

# Create and launch the application
if __name__ == "__main__":
    demo = create_demo()




    demo.launch(
        theme=gr.themes.Soft(primary_hue="blue"),
        footer_links=[{"label": "Built with anycoder", "url": "https://huggingface.co/spaces/akhaliq/anycoder"}],
        allowed_paths=["*"]

    )

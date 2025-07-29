import pandas as pd
import numpy as np
import re
from typing import Dict, List, Tuple

def normalize_column_names(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict, Dict]:
    """
    Normalize column names to be SQL and code friendly.
    Returns:
    - DataFrame with normalized columns
    - Mapping from original to normalized names
    - Mapping from normalized to original names
    """
    def normalize_name(name: str) -> str:
        # Convert to lowercase and replace spaces/special chars with underscore
        normalized = re.sub(r'[^a-zA-Z0-9]', '_', str(name).lower())
        # Remove consecutive underscores
        normalized = re.sub(r'_+', '_', normalized)
        # Remove leading/trailing underscores
        normalized = normalized.strip('_')
        return normalized
    
    # Create mappings
    name_mapping = {col: normalize_name(col) for col in df.columns}
    reverse_mapping = {v: k for k, v in name_mapping.items()}
    
    # Rename columns
    df_normalized = df.rename(columns=name_mapping)
    return df_normalized, name_mapping, reverse_mapping

def analyze_variable(series: pd.Series) -> Dict:
    """
    Analyze a variable's characteristics and suggest its type.
    Returns detailed statistics and type inference.
    """
    print(f"\nAnalyzing {series.name}:")
    
    # Basic stats
    stats = {
        'missing_count': int(series.isna().sum()),
        'missing_percent': float(series.isna().mean() * 100),
        'unique_count': int(series.nunique()),
        'total_count': len(series)
    }
    
    # Get clean sample values
    non_null = series.dropna()
    if len(non_null) > 0:
        stats['sample_values'] = non_null.unique()[:3].tolist()
        print(f"Sample values: {stats['sample_values']}")
    else:
        stats['sample_values'] = []
        print("No non-null values found")
        return {
            'type': 'categorical',
            'subtype': 'empty',
            'confidence': 1.0,
            'stats': stats
        }
    
    # Try numeric conversion
    try:
        # First clean the strings
        cleaned = non_null.astype(str).replace('[\$,%]', '', regex=True)
        print(f"Cleaned values: {cleaned.head().tolist()}")
        
        # Try converting to numeric
        numeric = pd.to_numeric(cleaned, errors='coerce')
        valid_numeric = numeric.dropna()
        numeric_ratio = len(valid_numeric) / len(non_null)
        print(f"Numeric ratio: {numeric_ratio:.2%}")
        
        if numeric_ratio > 0.95:  # Mostly numeric
            # Get numeric stats
            unique_values = sorted(valid_numeric.unique())
            min_val = float(min(unique_values))
            max_val = float(max(unique_values))
            print(f"Numeric range: {min_val} to {max_val}")
            
            # Check for decimals
            has_decimals = any('.' in str(x) for x in unique_values)
            print(f"Has decimals: {has_decimals}")
            
            # Check for small integers
            is_small_integers = all(float(x).is_integer() for x in unique_values)
            print(f"Is small integers: {is_small_integers}")
            
            # If it looks like a rating scale (1-5, 1-10)
            if is_small_integers and max_val <= 10 and min_val >= 0 and len(unique_values) <= 10:
                print("Detected as: numerical (rating scale)")
                return {
                    'type': 'numerical',  # Changed to numerical since it's ordered
                    'subtype': 'rating_scale',
                    'confidence': 0.9,
                    'stats': stats,
                    'range': [min_val, max_val],
                    'unique_values': unique_values
                }
            
            # If it has decimals or a wide range, it's continuous
            if has_decimals or (max_val - min_val) > 10:
                print("Detected as: numerical (continuous)")
                return {
                    'type': 'numerical',
                    'subtype': 'continuous',
                    'confidence': 0.9,
                    'stats': stats,
                    'range': [min_val, max_val]
                }
            
            # Small range of integers
            print("Detected as: numerical (discrete)")
            return {
                'type': 'numerical',
                'subtype': 'discrete',
                'confidence': 0.8,
                'stats': stats,
                'range': [min_val, max_val],
                'unique_values': unique_values
            }
            
    except Exception as e:
        print(f"Numeric conversion failed: {str(e)}")
    
    # Non-numeric analysis
    unique_ratio = stats['unique_count'] / stats['total_count']
    unique_values = sorted(non_null.unique())[:10]
    
    # If it has few unique values, it's categorical
    if unique_ratio < 0.05 or stats['unique_count'] <= 10:
        print("Detected as: categorical (nominal)")
        return {
            'type': 'categorical',
            'subtype': 'nominal',
            'confidence': 0.8,
            'stats': stats,
            'unique_values': unique_values
        }
    
    # High cardinality - might be IDs or free text
    print("Detected as: categorical (high cardinality)")
    return {
        'type': 'categorical',
        'subtype': 'high_cardinality',
        'confidence': 0.6,
        'stats': stats,
        'unique_values': unique_values
    }

def infer_column_types(df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Analyze all columns in a dataframe and infer their types.
    Returns a dictionary with detailed analysis for each column.
    """
    column_analysis = {}
    for column in df.columns:
        column_analysis[column] = analyze_variable(df[column])
    return column_analysis

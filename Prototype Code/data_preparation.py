import pandas as pd
import numpy as np
from typing import Dict, List
import streamlit as st
import logging
from datetime import datetime

def setup_logging():
    """Setup logging configuration"""
    log = st.empty()
    
    def log_message(message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log.markdown(f"**{timestamp}** - {message}")
    
    return log_message

def prepare_analysis_data(df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Prepare data for analysis based on user configuration.
    This function is designed to be completely data-agnostic and scalable.
    """
    log = setup_logging()
    try:
        # Create a copy to avoid modifying original
        df_prep = df.copy()
        
        # Initial data state
        log("➡️ Starting data preparation")
        log(f"Initial shape: {df_prep.shape}")
        
        # Memory state check
        log(f"Memory usage: {df_prep.memory_usage().sum() / 1024 / 1024:.2f} MB")
        
        # 1. Handle categorical variables
        log("\n🔄 Processing categorical variables...")
        categorical_dummies = []
        
        for col in config['categorical_variables']:
            log(f"\nProcessing {col}:")
            details = config['variable_details'].get(col, {})
            
            # Log pre-transformation state
            log(f"- Unique values before: {df_prep[col].unique().tolist()}")
            log(f"- Missing values: {df_prep[col].isna().sum()}")
            
            # Fill missing values with special category
            df_prep[col] = df_prep[col].fillna('MISSING')
            
            if details.get('has_order'):
                log(f"- Handling as ordered categorical with order: {details['value_order']}")
                value_order = details['value_order']
                # Create numeric mapping based on order
                value_map = {val: idx for idx, val in enumerate(value_order)}
                # Handle values not in mapping
                df_prep[col] = df_prep[col].map(lambda x: value_map.get(str(x), -1))
                log(f"- Mapped to numeric values: {value_map}")
            else:
                log("- Handling as unordered categorical")
                # Create dummy variables and ensure they're numeric
                dummies = pd.get_dummies(df_prep[col], prefix=col).astype(float)
                categorical_dummies.append(dummies)
                log(f"- Created dummies: {dummies.columns.tolist()}")
            
            log(f"- Shape after processing: {df_prep.shape}")
        
        # Combine all dummy variables
        if categorical_dummies:
            df_prep = pd.concat([df_prep] + categorical_dummies, axis=1)
        
        # 2. Handle numerical variables
        log("\n🔢 Processing numerical variables...")
        for col in config['numerical_variables']:
            log(f"\nProcessing {col}:")
            details = config['variable_details'].get(col, {})
            direction = details.get('direction')
            
            try:
                # Log pre-transformation state
                log(f"- Original values (sample): {df_prep[col].head().tolist()}")
                log(f"- Direction: {direction}")
                
                # Convert to numeric, handling special characters
                df_prep[col] = pd.to_numeric(
                    df_prep[col].astype(str).replace('[^0-9.-]', '', regex=True), 
                    errors='coerce'
                )
                log(f"- After numeric conversion: {df_prep[col].head().tolist()}")
                
                # Handle direction
                if direction == 'Lower values are better':
                    log("- Inverting values (lower is better)")
                    max_val = df_prep[col].max()
                    df_prep[col] = max_val - df_prep[col]
                    log(f"- After inversion: {df_prep[col].head().tolist()}")
                
                # Fill missing values with median
                median_val = df_prep[col].median()
                missing_count = df_prep[col].isna().sum()
                if missing_count > 0:
                    log(f"- Filling {missing_count} missing values with median: {median_val}")
                df_prep[col] = df_prep[col].fillna(median_val)
                
                # Scale values to 0-1 range
                min_val = df_prep[col].min()
                max_val = df_prep[col].max()
                if min_val != max_val:
                    df_prep[col] = (df_prep[col] - min_val) / (max_val - min_val)
                    log("- Scaled to 0-1 range")
                
                # Final state check
                log(f"- Final numeric range: [{df_prep[col].min()}, {df_prep[col].max()}]")
                
            except Exception as col_error:
                log(f"❌ Error processing {col}: {str(col_error)}")
                raise ValueError(f"Failed to process column {col}: {str(col_error)}")
        
        # 3. Handle target variable
        log("\n🎯 Processing target variable...")
        target_var = config['target_variable']
        log(f"- Target variable: {target_var}")
        log(f"- Original values: {df_prep[target_var].value_counts().to_dict()}")
        
        # Convert target to numeric, handling various binary formats
        target_values = df_prep[target_var].unique()
        if len(target_values) > 2:
            raise ValueError(f"Target variable must be binary. Found values: {target_values}")
            
        # Handle various binary formats (yes/no, true/false, 1/0)
        if df_prep[target_var].dtype == 'object':
            # Convert common binary string formats to 1/0
            df_prep[target_var] = df_prep[target_var].map(lambda x: 
                1 if str(x).lower() in ['1', 'true', 'yes', 'y', 't'] else 0
            )
        else:
            # For numeric formats, ensure binary 1/0
            df_prep[target_var] = pd.to_numeric(df_prep[target_var], errors='coerce')
            if not set(df_prep[target_var].unique()).issubset({0, 1, np.nan}):
                raise ValueError(f"Target values must be binary (0/1). Found: {df_prep[target_var].unique()}")
        
        log(f"- After conversion: {df_prep[target_var].value_counts().to_dict()}")
        
        # 4. Drop original categorical columns
        log("\n🗑️ Cleaning up...")
        df_prep = df_prep.drop(columns=config['categorical_variables'])
        log(f"- Removed original categorical columns: {config['categorical_variables']}")
        
        # 5. Keep only relevant columns
        keep_cols = (
            [target_var] + 
            config['numerical_variables'] + 
            [col for col in df_prep.columns if any(
                col.startswith(f"{cat}_") for cat in config['categorical_variables']
            )]
        )
        df_prep = df_prep[keep_cols]
        log("\n📊 Final dataset:")
        log(f"- Shape: {df_prep.shape}")
        log(f"- Columns: {df_prep.columns.tolist()}")
        log(f"- Memory usage: {df_prep.memory_usage().sum() / 1024 / 1024:.2f} MB")
        
        # 6. Validation
        log("\n✅ Running validation...")
        validate_prepared_data(df_prep, config)
        
        return df_prep
        
    except Exception as e:
        log(f"❌ Error in data preparation: {str(e)}")
        raise

def validate_prepared_data(df: pd.DataFrame, config: Dict) -> None:
    """Validate the prepared dataset"""
    log = setup_logging()
    target = config['target_variable']
    
    # Check for missing values
    null_counts = df.isnull().sum()
    if null_counts.any():
        log("❌ Found missing values:")
        for col in null_counts[null_counts > 0].index:
            log(f"- {col}: {null_counts[col]} missing values")
        raise ValueError(f"Dataset contains missing values")
    else:
        log("✅ No missing values found")
    
    # Check that all columns are numeric
    non_numeric = []
    for col in df.columns:
        try:
            pd.to_numeric(df[col])
        except:
            non_numeric.append(col)
    
    if non_numeric:
        log(f"❌ Found non-numeric columns: {non_numeric}")
        raise ValueError(f"Non-numeric values found")
    else:
        log("✅ All columns are numeric")
    
    # Validate target variable
    unique_targets = sorted(df[target].unique())
    log(f"Target variable values: {unique_targets}")
    if not set(unique_targets).issubset({0, 1}):
        log(f"❌ Invalid target values found: {unique_targets}")
        raise ValueError(f"Target must be binary (0/1)")
    else:
        log("✅ Target variable is valid binary")
    
    # Check for constant columns
    constant_cols = [col for col in df.columns if df[col].nunique() == 1]
    if constant_cols:
        log(f"❌ Found constant columns: {constant_cols}")
        raise ValueError(f"Constant columns found")
    else:
        log("✅ No constant columns found")
    
    # Check for highly correlated features
    if len(df.columns) > 2:  # Need at least 2 features plus target
        corr_matrix = df.drop(columns=[target]).corr().abs()
        high_corr = np.where(np.triu(corr_matrix, k=1) > 0.95)
        high_corr_pairs = [
            (corr_matrix.index[i], corr_matrix.columns[j])
            for i, j in zip(*high_corr)
        ]
        if high_corr_pairs:
            log("⚠️ Warning: Found highly correlated features:")
            for col1, col2 in high_corr_pairs:
                log(f"- {col1} and {col2}")
    
    log("✅ All validations passed")

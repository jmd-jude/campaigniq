import streamlit as st
import pandas as pd
from lib.snowflake_utils import init_connection
from lib.analysis import run_analysis
from lib.data_utils import analyze_variable, infer_column_types

def load_data_from_snowflake(table_name: str) -> pd.DataFrame:
    """Load data from Snowflake table"""
    conn = init_connection()
    cur = conn.cursor()

    try:
        # Load data from table
        cur.execute(f"SELECT * FROM {table_name}")
        columns = [desc[0] for desc in cur.description]
        data = cur.fetchall()
        return pd.DataFrame(data, columns=columns)
    finally:
        cur.close()
        conn.close()

def configure_categorical_var(df: pd.DataFrame, var: str) -> dict:
    """Configure a categorical variable"""
    # Handle None/NaN values
    unique_values = df[var].dropna().unique().tolist()
    unique_values = sorted([str(x) for x in unique_values if x is not None])
    
    st.write(f"Unique values: {', '.join(unique_values)}")
    has_order = st.checkbox("This variable has a meaningful order", key=f"order_{var}")
    
    details = {"type": "categorical"}
    
    if has_order:
        value_order = st.multiselect(
            "Arrange values from best to worst",
            options=unique_values,
            default=unique_values,
            key=f"order_{var}"
        )
        details["has_order"] = True
        details["value_order"] = value_order
    else:
        details["has_order"] = False
    
    return details

def configure_numerical_var(df: pd.DataFrame, var: str) -> dict:
    """Configure a numerical variable"""
    numeric_values = pd.to_numeric(df[var], errors='coerce')
    value_range = [float(numeric_values.min()), float(numeric_values.max())]
    st.write(f"Value range: {value_range[0]} to {value_range[1]}")
    
    direction = st.radio(
        "Interpret values as:",
        options=["Higher values are better", "Lower values are better"],
        key=f"direction_{var}"
    )
    
    return {
        "type": "numerical",
        "direction": direction,
        "range": value_range
    }

def show():
    """Configure analysis settings"""
    st.subheader("Configure Analysis")
    
    # Check for valid upload
    if 'table_name' not in st.session_state:
        st.warning("Please upload data first")
        return False
        
    # Load fresh data from Snowflake
    try:
        df = load_data_from_snowflake(st.session_state.table_name)
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return False
    
    # Initialize step if not in session state
    if 'config_step' not in st.session_state:
        st.session_state.config_step = 1
    
    # Progress indicator
    st.progress(st.session_state.config_step / 2)
    
    if st.session_state.config_step == 1:
        st.write("### Step 1: Variable Selection")
        
        # Target Variable Selection
        st.write("#### Select Target Variable")
        st.write("Choose the outcome variable you want to predict (must be binary 0/1).")
        
        # Add empty option as first choice
        target_options = [""] + df.columns.tolist()
        target_var = st.selectbox(
            "Target Variable",
            options=target_options,
            help="This should be a binary (0/1) outcome you want to predict"
        )
        
        if target_var:
            # Show target distribution
            target_dist = df[target_var].value_counts()
            st.write("Target Distribution:")
            st.write(target_dist)
            
            # Validate binary target
            try:
                target_values = pd.to_numeric(df[target_var], errors='coerce')
                unique_values = target_values.dropna().unique()
                if not set(unique_values).issubset({0, 1}):
                    st.error("Target variable must contain only 0 and 1 values")
                    return False
            except:
                st.error("Target variable must be numeric (0/1)")
                return False
            
            # Analyze remaining variables
            st.write("### Variable Analysis")
            st.write("Review each variable's characteristics:")
            
            available_vars = [c for c in df.columns if c != target_var]
            variable_analysis = {var: analyze_variable(df[var]) for var in available_vars}
            
            # Group variables by suggested type
            suggested_categorical = [
                var for var in available_vars
                if variable_analysis[var]['type'] == 'categorical'
            ]
            suggested_numerical = [
                var for var in available_vars
                if variable_analysis[var]['type'] == 'numerical'
            ]
            
            # Let user confirm classifications
            st.write("### Confirm Variable Types")
            col1, col2 = st.columns(2)
            with col1:
                categorical_vars = st.multiselect(
                    "Categorical Variables",
                    options=available_vars,
                    default=suggested_categorical,
                    help="Variables with discrete categories"
                )
            with col2:
                remaining_vars = [v for v in available_vars if v not in categorical_vars]
                numerical_vars = st.multiselect(
                    "Numerical Variables",
                    options=remaining_vars,
                    default=[v for v in suggested_numerical if v in remaining_vars],
                    help="Variables with continuous values"
                )
            
            if st.button("Continue to Variable Details"):
                st.session_state.target_var = target_var
                st.session_state.categorical_vars = categorical_vars
                st.session_state.numerical_vars = numerical_vars
                st.session_state.config_step = 2
                st.rerun()
        else:
            st.info("Please select a target variable")
    
    elif st.session_state.config_step == 2:
        st.write("### Step 2: Variable Details")
        
        variable_details = {}
        
        if st.session_state.categorical_vars:
            st.write("#### Categorical Variables")
            st.write("For each categorical variable, specify if the values have a meaningful order.")
            
            for var in st.session_state.categorical_vars:
                with st.expander(f"Configure {var}"):
                    variable_details[var] = configure_categorical_var(df, var)
        
        if st.session_state.numerical_vars:
            st.write("#### Numerical Variables")
            st.write("For each numerical variable, specify how to interpret the values.")
            
            for var in st.session_state.numerical_vars:
                with st.expander(f"Configure {var}"):
                    variable_details[var] = configure_numerical_var(df, var)
        
        if st.button("Start Analysis", type="primary"):
            try:
                # Clear any existing results
                for key in ['analysis_results', 'page']:
                    if key in st.session_state:
                        del st.session_state[key]
                
                # Create analysis config
                config = {
                    "target_variable": st.session_state.target_var,
                    "categorical_variables": st.session_state.categorical_vars,
                    "numerical_variables": st.session_state.numerical_vars,
                    "variable_details": variable_details,
                    "source_table": st.session_state.table_name
                }
                
                # Initialize connection
                conn = init_connection()
                
                try:
                    # Run analysis
                    with st.spinner('Running analysis...'):
                        result = run_analysis(conn, config)
                    
                    if result['success']:
                        st.success("✅ Analysis completed successfully!")
                        st.session_state['analysis_results'] = result
                        return True
                    else:
                        st.error(f"Analysis failed: {result['error']}")
                        return False
                        
                finally:
                    conn.close()
                    
            except Exception as e:
                st.error(f"Error running analysis: {str(e)}")
                return False
    
    # Add back button except for first step
    if st.session_state.config_step > 1:
        if st.button("← Back"):
            st.session_state.config_step -= 1
            st.rerun()
    
    return False

if __name__ == "__main__":
    show()

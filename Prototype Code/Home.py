import streamlit as st
from lib.snowflake_utils import init_connection, get_job_status

def show_connection_status():
    """Display Snowflake connection status"""
    try:
        conn = init_connection()
        st.sidebar.success("Connected as: JHOFFNER")
        return True
    except Exception as e:
        st.sidebar.error(f"Connection failed: {str(e)}")
        return False

def main():
    st.set_page_config(
        page_title="Predictive Analytics App",
        page_icon="📊",
        layout="wide"
    )
    
    # Title and description
    st.title("Predictive Analytics App")
    
    # Connection status in sidebar
    st.sidebar.write("Connection Status:")
    connected = show_connection_status()
    
    if not connected:
        st.error("Please check your Snowflake connection settings.")
        return
    
    # Main content
    st.write("""
    ### Welcome to the Predictive Analytics App
    
    This application helps you build and analyze predictive models using your data. 
    Follow these steps to get started:
    
    1. **Upload Data**: Upload your CSV file containing the data you want to analyze.
       - Minimum 2,000 rows recommended
       - At least 3 variables required
       - Include a binary target variable (0/1)
    
    2. **Configure Analysis**: Set up your analysis parameters.
       - Select target variable
       - Configure variable types
       - Set analysis options
    
    3. **Review Results**: Examine the analysis outputs.
       - Model performance metrics
       - Feature importance analysis
       - Response rate analysis
       - Detailed insights
    """)
    
    # Data requirements
    with st.expander("Data Requirements"):
        st.write("""
        #### Required Data Format
        - **File Type**: CSV (Comma Separated Values)
        - **Size**: 2,000+ rows recommended for reliable results
        - **Variables**: Minimum 3 variables (columns)
        - **Target**: Binary outcome variable (0/1, Yes/No, True/False)
        
        #### Supported Variable Types
        - **Categorical**: Variables with discrete categories (e.g., gender, state)
        - **Numerical**: Variables with continuous values (e.g., age, income)
        - **Binary**: Yes/No or True/False variables
        
        #### Data Quality Guidelines
        - Remove any sensitive or identifying information
        - Ensure consistent formatting across variables
        - Handle missing values before upload if possible
        - Remove duplicate records if not meaningful
        """)
    
    # Analysis capabilities
    with st.expander("Analysis Capabilities"):
        st.write("""
        #### Model Types
        - Binary classification models
        - Automated feature engineering
        - Handling of categorical variables
        - Missing value imputation
        
        #### Analysis Outputs
        - Model performance metrics (AUC, precision, recall)
        - Feature importance analysis
        - Response rate analysis by decile
        - Detailed variable insights
        
        #### Visualization Options
        - ROC curves
        - Precision-Recall curves
        - Feature importance plots
        - Response rate charts
        """)
    
    # Example use cases
    with st.expander("Example Use Cases"):
        st.write("""
        #### Common Applications
        1. **Customer Response Prediction**
           - Predict likelihood of purchase
           - Identify high-value customers
           - Optimize marketing campaigns
        
        2. **Risk Assessment**
           - Credit risk evaluation
           - Fraud detection
           - Default prediction
        
        3. **Behavior Analysis**
           - Customer churn prediction
           - Product adoption likelihood
           - Service usage patterns
        
        4. **Campaign Optimization**
           - Response likelihood scoring
           - Audience segmentation
           - Channel effectiveness
        """)
    
    # Get started button
    st.write("---")
    col1, col2, col3 = st.columns([2,1,2])
    with col2:
        if st.button("Get Started", type="primary"):
            st.switch_page("pages/1_upload.py")

if __name__ == "__main__":
    main()

import streamlit as st
import pandas as pd
from datetime import datetime
from lib.snowflake_utils import init_connection
from lib.validation import validate_data
from lib.data_utils import normalize_column_names, infer_column_types

def show():
    st.subheader("Upload Data")

    # File upload with clear instructions
    st.markdown("""
    ### Instructions
    1. Upload a CSV file containing your data
    2. Review the preview and data types
    3. Confirm the data looks correct
    4. Proceed to configuration

    **Requirements:**
    - File must be in CSV format
    - Minimum 2000 rows recommended
    - Must include at least 3 variables
    - Please ensure your CSV file contains only the variables you want to analyze. Remove any record IDs, timestamps, or other non-analytical fields before uploading.
    """)

    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type="csv",
        help="Upload your data in CSV format. Maximum file size: 200MB"
    )

    if uploaded_file is not None:
        try:
            # Read data with progress indicator
            with st.spinner('Reading file...'):
                df = pd.read_csv(uploaded_file)

            # Initial data validation
            if len(df) < 2000:
                st.warning("⚠️ Your dataset has fewer than 2000 rows. While you can proceed, larger datasets typically provide better results.")

            if len(df.columns) < 3:
                st.error("❌ Your dataset must have at least 3 columns for analysis.")
                return False

            # Normalize column names and store mappings
            with st.spinner('Processing data...'):
                df_normalized, name_mapping, reverse_mapping = normalize_column_names(df)
                st.session_state.name_mapping = name_mapping
                st.session_state.reverse_mapping = reverse_mapping

                # Infer column types
                column_analysis = infer_column_types(df_normalized)

            # Data Overview Section
            st.write("### Data Overview")

            # Basic statistics in a cleaner layout
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Rows", f"{df.shape[0]:,}")
            with col2:
                st.metric("Total Columns", df.shape[1])
            with col3:
                st.metric("File Size", f"{round(uploaded_file.size/1e6, 2)} MB")
            with col4:
                st.metric("Missing Values", f"{df.isna().sum().sum():,}")

            # Data Preview
            st.write("### Data Preview")
            st.dataframe(
                df.head(),
                use_container_width=True
            )

            # Column Information
            st.write("### Column Information")
            col_info = []
            for col in df.columns:
                analysis = column_analysis[name_mapping[col]]
                stats = analysis['stats']
                
                col_info.append({
                    "Column Name": col,
                    "Type": f"{analysis['type'].title()} ({analysis['confidence']*100:.0f}% confidence)",
                    "Missing Values": f"{stats['missing_count']:,} ({stats['missing_percent']:.1f}%)",
                    "Unique Values": f"{stats['unique_count']:,}",
                    "Sample Values": ", ".join(map(str, stats['sample_values']))
                })
            
            st.dataframe(
                pd.DataFrame(col_info),
                use_container_width=True
            )

            # Proceed button with validation
            st.write("### Upload File")
            proceed_col1, proceed_col2 = st.columns([3, 1])
            with proceed_col1:
                st.write("""
                By proceeding you confirm that:
                - The data preview looks correct
                - Column names are properly recognized
                - The inferred data types are appropriate
                """)
            with proceed_col2:
                if st.button("Proceed to Configure", type="primary"):
                    with st.spinner('Saving data...'):
                        # Create connection and save to Snowflake
                        conn = init_connection()
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        st.session_state.df = df_normalized
                        st.session_state.timestamp = timestamp

                        # Create progress bar
                        progress_bar = st.progress(0)

                        # Validate and save data
                        result = validate_data(conn, df_normalized, timestamp, progress_bar)

                        if result['success']:
                            st.success("✅ Data successfully uploaded! Proceeding to configuration...")
                            st.session_state.table_name = result['table_name']
                            return True
                        else:
                            st.error(f"❌ Error: {result['error']}")

        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")
            st.write("Please ensure your file is a valid CSV and try again.")

    return False

if __name__ == "__main__":
    show()

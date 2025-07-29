import pandas as pd
from typing import Dict, Any, Optional
import streamlit as st
from datetime import datetime

def validate_data(conn: Any, df: pd.DataFrame, timestamp: str, progress_bar: Optional[Any] = None) -> Dict[str, Any]:
    """
    Validate and save data to Snowflake.
    Keeps data in original format for flexibility.
    """
    try:
        if progress_bar:
            progress_bar.progress(0)
            
        # 1. Basic structural checks
        if progress_bar:
            progress_bar.progress(10)
            
        # Check minimum rows (100 for basic statistical significance)
        if len(df) < 100:
            return {
                'success': False,
                'error': f"Dataset too small. Minimum 100 rows required, got {len(df)}"
            }
            
        # Check minimum columns (need at least predictors + outcome)
        if len(df.columns) < 2:
            return {
                'success': False,
                'error': f"Not enough variables. Minimum 2 columns required (predictors + outcome), got {len(df.columns)}"
            }
            
        # 2. Data quality checks
        if progress_bar:
            progress_bar.progress(30)
            
        # Check for completely empty columns
        empty_cols = [
            col for col in df.columns
            if df[col].isnull().all()
        ]
        if empty_cols:
            return {
                'success': False,
                'error': f"Found completely empty columns: {', '.join(empty_cols)}"
            }
            
        # 3. Create table name
        if progress_bar:
            progress_bar.progress(50)
            
        table_name = f"UPLOAD_{timestamp}"
        
        # 4. Save to Snowflake
        if progress_bar:
            progress_bar.progress(70)
            
        try:
            # Create cursor
            cur = conn.cursor()
            
            # Use database
            cur.execute("USE DATABASE PREDICTIVE_ANALYTICS")
            
            # Create schema if not exists
            cur.execute("CREATE SCHEMA IF NOT EXISTS RAW_DATA")
            
            # Create table with all columns as VARCHAR
            columns = [f'"{col}" VARCHAR' for col in df.columns]
            
            create_table_sql = f"""
            CREATE OR REPLACE TABLE RAW_DATA.{table_name} (
                {', '.join(columns)}
            )
            """
            cur.execute(create_table_sql)
            
            # Insert data
            if progress_bar:
                progress_bar.progress(80)
                
            # Convert all values to strings, handling None/NaN
            rows = []
            for _, row in df.iterrows():
                rows.append([str(val) if pd.notna(val) else None for val in row])
            
            # Batch insert
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                placeholders = ','.join(['(' + ','.join(['%s'] * len(df.columns)) + ')'] * len(batch))
                values = [val for row in batch for val in row]
                cur.execute(f"INSERT INTO RAW_DATA.{table_name} VALUES {placeholders}", values)
            
            # Save data quality metrics
            if progress_bar:
                progress_bar.progress(90)
                
            # Calculate basic metrics using Snowflake
            metrics_sql = f"""
                INSERT INTO METADATA.DATA_QUALITY (
                    job_id,
                    metrics,
                    created_at
                )
                SELECT
                    %s,
                    OBJECT_CONSTRUCT(
                        'timestamp', %s,
                        'table_name', %s,
                        'metrics', OBJECT_CONSTRUCT(
                            'total_rows', (SELECT COUNT(*) FROM RAW_DATA.{table_name}),
                            'total_columns', {len(df.columns)},
                            'column_stats', (
                                SELECT OBJECT_AGG(column_name, stats)
                                FROM (
                                    SELECT 
                                        column_name,
                                        OBJECT_CONSTRUCT(
                                            'non_null_count', non_null_count,
                                            'unique_count', unique_count
                                        ) as stats
                                    FROM (
                                        {' UNION ALL '.join([
                                            f"""
                                            SELECT 
                                                '{col}' as column_name,
                                                COUNT("{col}") as non_null_count,
                                                COUNT(DISTINCT "{col}") as unique_count
                                            FROM RAW_DATA.{table_name}
                                            """
                                            for col in df.columns
                                        ])}
                                    )
                                )
                            )
                        )
                    ),
                    CURRENT_TIMESTAMP()
            """
            cur.execute(metrics_sql, (timestamp, timestamp, table_name))
            
            # Create job record
            cur.execute("""
                INSERT INTO METADATA.JOBS (
                    job_id,
                    status,
                    created_at
                ) VALUES (%s, 'UPLOADED', CURRENT_TIMESTAMP())
            """, (timestamp,))
            
            conn.commit()
            
            if progress_bar:
                progress_bar.progress(100)
                
            return {
                'success': True,
                'table_name': f"RAW_DATA.{table_name}"
            }
            
        except Exception as e:
            conn.rollback()
            return {
                'success': False,
                'error': f"Database error: {str(e)}"
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': f"Validation error: {str(e)}"
        }

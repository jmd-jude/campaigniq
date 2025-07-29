import os
from snowflake import connector
from cryptography.fernet import Fernet
import streamlit as st
from typing import Any, Optional, Tuple

def init_connection():
    """Initialize Snowflake connection with auto-reconnect"""
    try:
        return connector.connect(
            user=st.secrets["snowflake"]["user"],
            password=st.secrets["snowflake"]["password"],
            account=st.secrets["snowflake"]["account"],
            warehouse=st.secrets["snowflake"]["warehouse"],
            database=st.secrets["snowflake"]["database"],
            schema=st.secrets["snowflake"]["schema"],
            client_session_keep_alive=True,  # Keep session alive
            autocommit=False  # Explicit transaction control
        )
    except Exception as e:
        print(f"Error connecting to Snowflake: {str(e)}")
        raise

def execute_with_retry(conn: Any, operation: Tuple[str, Optional[Any]], max_retries=3):
    """Execute a Snowflake operation with retry logic"""
    sql, params = operation
    
    # Convert ? to %s for Snowflake
    sql = sql.replace('?', '%s')
    
    for attempt in range(max_retries):
        try:
            cursor = conn.cursor()
            try:
                if isinstance(params, list):
                    cursor.executemany(sql, params)
                else:
                    cursor.execute(sql, params)
                conn.commit()
                return cursor
            except Exception as e:
                conn.rollback()
                raise
            finally:
                cursor.close()
        except connector.errors.OperationalError as e:
            if attempt == max_retries - 1:
                raise
            print(f"Connection error, retrying... ({attempt + 1}/{max_retries})")
            conn = init_connection()  # Get fresh connection
    return None

def get_job_status(conn: Any, job_id: str) -> dict:
    """Get the status of a job from Snowflake"""
    try:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT status, error_message FROM METADATA.JOBS WHERE job_id = %s",
                (job_id,)
            )
            result = cursor.fetchone()
            return {
                'status': result[0] if result else 'NOT_FOUND',
                'error': result[1] if result and len(result) > 1 else None
            }
        finally:
            cursor.close()
    except Exception as e:
        print(f"Error getting job status: {str(e)}")
        return {'status': 'ERROR', 'error': str(e)}

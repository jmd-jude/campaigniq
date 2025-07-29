import pandas as pd
import numpy as np
import json
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from typing import Dict, Any, Callable, Optional
from lib.scoring import generate_scoring_rules, apply_scoring_rules, format_rule_description

def interpret_feature_importance(feature_importance_df: pd.DataFrame, config: Dict) -> pd.DataFrame:
    """
    Interpret feature importance considering variable details.
    Handles any variable configuration provided by the user.
    """
    variable_details = config['variable_details']
    
    # Add interpretation context
    feature_importance_df['effect'] = feature_importance_df.apply(
        lambda row: 'positive' if row['coefficient'] > 0 else 'negative',
        axis=1
    )
    
    return feature_importance_df

def save_model_details(cursor: Any, job_id: str, model: LogisticRegression, feature_names: list) -> None:
    """Save model details to database"""
    print("Saving model details...")
    
    # Convert numpy arrays to lists and format as JSON objects
    coefficients = {
        'values': [float(x) for x in model.coef_[0]]  # Convert to Python floats
    }
    features = {
        'names': feature_names
    }
    
    # Use SELECT with PARSE_JSON for VARIANT columns
    cursor.execute('''
        INSERT INTO RESULTS.MODEL_DETAILS (
            job_id, model_type, coefficients, intercept, features
        )
        SELECT 
            %s,
            %s,
            PARSE_JSON(%s),
            %s,
            PARSE_JSON(%s)
    ''', (
        job_id,
        'logistic_regression',
        json.dumps(coefficients),
        float(model.intercept_[0]),
        json.dumps(features)
    ))
    print("✓ Model details saved")

def save_model_metrics(cursor: Any, job_id: str, baseline_rate: float, top_decile_rate: float) -> None:
    """Save model metrics to database"""
    print("Saving model metrics...")
    cursor.execute('''
        INSERT INTO RESULTS.MODEL_METRICS (
            job_id, baseline_rate, top_decile_rate
        ) VALUES (%s, %s, %s)
    ''', (job_id, baseline_rate, top_decile_rate))
    print("✓ Model metrics saved")

def save_scoring_rules(cursor: Any, job_id: str, scoring_rules: list) -> None:
    """Save scoring rules to database"""
    print("Saving scoring rules...")
    for rule in scoring_rules:
        cursor.execute('''
            INSERT INTO RESULTS.SCORING_RULES (
                job_id, variable, rule, impact
            ) VALUES (
                %s,
                %s,
                %s,
                %s
            )
        ''', (
            job_id,
            rule['variable'],
            rule['condition'],  # Map condition to rule
            float(rule['adjustment'])  # Map adjustment to impact
        ))
    print(f"✓ Saved {len(scoring_rules)} scoring rules")

def save_response_rates(cursor: Any, job_id: str, response_rates: pd.DataFrame) -> None:
    """Save response rates to database"""
    print("Saving response rates...")
    for _, row in response_rates.iterrows():
        cursor.execute('''
            INSERT INTO RESULTS.RESPONSE_RATES (
                job_id, decile, count, response_rate, lift
            ) VALUES (%s, %s, %s, %s, %s)
        ''', (
            job_id,
            row['decile'],
            int(row['count']),  # Column is named 'count' not 'record_count'
            float(row['response_rate']),
            float(row['lift'])
        ))
    print(f"✓ Saved {len(response_rates)} response rate records")

def save_scored_records(cursor: Any, job_id: str, regression_scores: np.ndarray, simple_scores: np.ndarray, deciles: pd.Series) -> None:
    """Save scored records to database"""
    print("Saving scored records...")
    for i in range(len(regression_scores)):
        cursor.execute('''
            INSERT INTO RESULTS.SCORED_RECORDS (
                job_id, record_id, regression_score, simple_score, decile
            ) VALUES (%s, %s, %s, %s, %s)
        ''', (
            job_id,
            i,
            float(regression_scores[i]),
            float(simple_scores[i]),
            deciles[i]
        ))
        if (i + 1) % 100 == 0:  # Commit every 100 records
            print(f"✓ Saved {i + 1} scored records")
    print(f"✓ Saved all {len(regression_scores)} scored records")

def run_analysis(conn: Any, config: Dict, progress_callback: Optional[Callable] = None) -> Dict:
    """
    Run the analysis pipeline with business-friendly outputs.
    Focused on actionable insights for SMB users.
    """
    cursor = None
    try:
        if progress_callback:
            progress_callback(0, "Loading data...")
            
        # Load data from source table
        source_table = config.get('source_table')
        if not source_table:
            raise ValueError("Source table not specified in configuration")
        
        # Extract job_id from table name - keep full format
        job_id = source_table.replace('RAW_DATA.UPLOAD_', '')
            
        # Use fully qualified table name
        if not source_table.startswith('RAW_DATA.'):
            source_table = f'RAW_DATA.{source_table}'
            
        print(f"Loading data from {source_table}...")
        print(f"Using job ID: {job_id}")
        
        # Test query first
        cursor = conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM {source_table}')
        count = cursor.fetchone()[0]
        print(f"Found {count} records")
        
        if count == 0:
            raise ValueError(f"Table {source_table} is empty")
            
        # Now load the data
        cursor.execute(f'SELECT * FROM {source_table}')
        columns = [desc[0] for desc in cursor.description]
        print(f"Found columns: {', '.join(columns)}")
        
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=columns)
        print(f"Loaded {len(df)} records with {len(df.columns)} columns")
        
        if progress_callback:
            progress_callback(10, "Preparing features...")
            
        # Prepare data using data preparation pipeline
        try:
            print("Preparing features...")
            from lib.data_preparation import prepare_analysis_data
            df_prep = prepare_analysis_data(df, config)
            print(f"Prepared {len(df_prep.columns)} features")
        except Exception as prep_error:
            raise ValueError(f"Data preparation failed: {str(prep_error)}")
            
        # Get target variable and prepared features
        target_var = config['target_variable']
        y = df_prep[target_var]
        X = df_prep.drop(columns=[target_var])
        
        # Validate data size
        if len(X) < 100:  # Minimum sample size for reliable analysis
            raise ValueError(f"Insufficient data for analysis. Minimum 100 rows required, got {len(X)}")
            
        if progress_callback:
            progress_callback(30, "Training model...")
            
        print("Training model...")
        # Split and scale data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        # Train model with regularization to handle multicollinearity
        model = LogisticRegression(
            penalty='l1',
            solver='liblinear',
            random_state=42,
            max_iter=1000,
            tol=1e-4
        )
        model.fit(X_train_scaled, y_train)
        print("Model trained successfully")
        
        if progress_callback:
            progress_callback(50, "Analyzing features...")
            
        print("Analyzing features...")
        # Analyze features with interpretation
        feature_importance = pd.DataFrame({
            'variable': X.columns,
            'importance': abs(model.coef_[0]),
            'coefficient': model.coef_[0]
        }).sort_values('importance', ascending=False)
        
        # Add interpretation context
        feature_importance = interpret_feature_importance(feature_importance, config)
        print(f"Found {len(feature_importance)} important features")
        
        # Create new job
        print("Creating job record...")
        cursor.execute(
            """
            INSERT INTO METADATA.JOBS (job_id, status)
            VALUES (%s, 'RUNNING')
            """,
            (job_id,)
        )
        conn.commit()
        print("✓ Job status set to RUNNING")
        
        # Save model details
        save_model_details(cursor, job_id, model, X.columns.tolist())
        conn.commit()
        
        # Save feature importance records
        print("Saving feature importance...")
        feature_records = [
            (job_id, row['variable'], float(row['importance']), 
             float(row['coefficient']), row['effect'])
            for _, row in feature_importance.iterrows()
        ]
        
        for i, record in enumerate(feature_records, 1):
            cursor.execute('''
                INSERT INTO RESULTS.FEATURE_IMPORTANCE (
                    job_id, variable, importance, coefficient, effect
                ) VALUES (%s, %s, %s, %s, %s)
            ''', record)
            if i % 10 == 0:  # Commit every 10 records
                conn.commit()
                print(f"✓ Saved {i} feature records")
        conn.commit()  # Final commit
        print(f"✓ Saved all {len(feature_records)} feature records")
        
        # Generate scoring rules
        print("Generating scoring rules...")
        scoring_rules = generate_scoring_rules(
            df=df_prep,
            model_coefficients=model.coef_[0],
            feature_names=X.columns.tolist(),
            config=config
        )
        print(f"Generated {len(scoring_rules)} scoring rules")
        
        # Save scoring rules
        save_scoring_rules(cursor, job_id, scoring_rules)
        conn.commit()
        
        if progress_callback:
            progress_callback(70, "Calculating scores...")
            
        print("Calculating scores...")
        # Calculate regression scores
        regression_scores = model.predict_proba(scaler.transform(X))[:, 1]
        
        # Calculate simple scores
        simple_scores = apply_scoring_rules(df_prep, scoring_rules)
        print("Scores calculated")
        
        # Calculate deciles using regression scores
        deciles = pd.qcut(regression_scores, q=10, labels=['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10'])
        
        # Calculate response rates
        response_rates = pd.DataFrame({
            'decile': deciles.unique(),
            'count': pd.Series(y.values).groupby(deciles).count(),
            'response_rate': pd.Series(y.values).groupby(deciles).mean()
        }).reset_index(drop=True)
        
        # Calculate lift
        baseline_rate = y.mean()
        response_rates['lift'] = response_rates['response_rate'] / baseline_rate
        
        # Save model metrics
        save_model_metrics(cursor, job_id, float(baseline_rate), float(response_rates.iloc[-1]['response_rate']))
        conn.commit()
        
        # Save response rates
        save_response_rates(cursor, job_id, response_rates)
        conn.commit()
        
        # Save scored records
        save_scored_records(cursor, job_id, regression_scores, simple_scores, deciles)
        conn.commit()
        
        # Update job status
        print("Updating job status...")
        cursor.execute(
            """
            UPDATE METADATA.JOBS
            SET status = 'COMPLETED'
            WHERE job_id = %s
            """,
            (job_id,)
        )
        conn.commit()
        print("✓ Job status updated to COMPLETED")
        
        print("Analysis completed successfully")
            
        if progress_callback:
            progress_callback(100, "Analysis complete!")
            
        return {
            'success': True,
            'metrics': {
                'baseline_rate': float(baseline_rate),
                'top_decile_rate': float(response_rates.iloc[-1]['response_rate'])
            },
            'feature_importance': feature_importance.to_dict('records'),
            'scoring_rules': [format_rule_description(rule) for rule in scoring_rules],
            'response_rates': response_rates.to_dict('records')
        }
        
    except Exception as e:
        print(f"Error in analysis: {str(e)}")
        # Log error and update job status
        if 'job_id' in locals() and cursor:
            try:
                cursor.execute(
                    """
                    UPDATE METADATA.JOBS
                    SET status = 'FAILED',
                        error_message = %s
                    WHERE job_id = %s
                    """,
                    (str(e), job_id)
                )
                conn.commit()
            except Exception as update_error:
                print(f"Error updating job status: {str(update_error)}")
        
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        if cursor:
            cursor.close()

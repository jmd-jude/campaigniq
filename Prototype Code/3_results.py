import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json

def format_number(num):
    """Format numbers for display"""
    if isinstance(num, float):
        if abs(num) < 0.01:
            return f"{num:.4f}"
        return f"{num:.2f}"
    return str(num)

def show_performance_metrics(metrics):
    """Display model performance metrics"""
    st.write("### Model Performance")
    
    # Key metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "AUC Score",
            format_number(metrics['model_performance']['auc_score'])
        )
    
    with col2:
        st.metric(
            "Average Precision",
            format_number(metrics['model_performance']['avg_precision'])
        )
    
    with col3:
        st.metric(
            "Cross-Val AUC (Mean)",
            format_number(metrics['model_performance']['cv_scores']['mean'])
        )
    
    with col4:
        st.metric(
            "Baseline Rate",
            format_number(metrics['model_performance']['baseline_rate'])
        )

def show_feature_importance(feature_importance):
    """Display feature importance analysis"""
    st.write("### Feature Importance")
    
    # Convert to DataFrame if needed
    if isinstance(feature_importance, list):
        feature_importance = pd.DataFrame(feature_importance)
    
    # Sort by absolute importance
    feature_importance = feature_importance.sort_values('importance', ascending=True)
    
    # Create horizontal bar chart
    fig = go.Figure()
    
    # Add bars
    fig.add_trace(go.Bar(
        y=feature_importance['variable'],
        x=feature_importance['importance'],
        orientation='h',
        marker_color=feature_importance['coefficient'].apply(
            lambda x: 'rgb(55, 126, 184)' if x > 0 else 'rgb(228, 26, 28)'
        ),
        name='Importance'
    ))
    
    # Update layout
    fig.update_layout(
        title='Feature Importance',
        xaxis_title='Importance Score',
        yaxis_title='Feature',
        height=max(400, len(feature_importance) * 25),  # Dynamic height
        showlegend=False
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Feature details in expander
    with st.expander("Feature Details"):
        # Create detailed feature table
        feature_details = []
        for _, row in feature_importance.iterrows():
            interpretation = row['interpretation']
            if isinstance(interpretation, str):
                interpretation = json.loads(interpretation)
            
            details = {
                'Feature': row['variable'],
                'Importance': format_number(row['importance']),
                'Effect': 'Positive' if row['coefficient'] > 0 else 'Negative',
                'Direction': interpretation.get('direction', 'N/A'),
                'Impact': format_number(interpretation.get('impact', 0))
            }
            feature_details.append(details)
        
        st.dataframe(
            pd.DataFrame(feature_details),
            use_container_width=True
        )

def show_response_analysis(metrics):
    """Display response rate analysis"""
    st.write("### Response Analysis")
    
    # Create decile plot
    decile_data = pd.DataFrame({
        'Decile': [f'D{i+1}' for i in range(10)],
        'Response Rate': metrics['decile_analysis']['rates'],
        'Volume': metrics['decile_analysis']['volumes'],
        'Lift': metrics['decile_analysis']['lift']
    })
    
    # Response rate by decile
    fig_response = go.Figure()
    
    # Add response rate line
    fig_response.add_trace(go.Scatter(
        x=decile_data['Decile'],
        y=decile_data['Response Rate'],
        mode='lines+markers',
        name='Response Rate',
        line=dict(color='rgb(55, 126, 184)', width=2)
    ))
    
    # Add lift line on secondary y-axis
    fig_response.add_trace(go.Scatter(
        x=decile_data['Decile'],
        y=decile_data['Lift'],
        mode='lines+markers',
        name='Lift',
        line=dict(color='rgb(228, 26, 28)', width=2),
        yaxis='y2'
    ))
    
    # Update layout
    fig_response.update_layout(
        title='Response Rate and Lift by Decile',
        xaxis_title='Decile',
        yaxis_title='Response Rate',
        yaxis2=dict(
            title='Lift',
            overlaying='y',
            side='right'
        ),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig_response, use_container_width=True)
    
    # Decile details in expander
    with st.expander("Decile Details"):
        st.dataframe(decile_data, use_container_width=True)

def show_model_plots(metrics):
    """Display model performance plots"""
    st.write("### Model Performance Curves")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.plotly_chart(
            go.Figure(metrics['plots']['roc_curve']),
            use_container_width=True
        )
    
    with col2:
        st.plotly_chart(
            go.Figure(metrics['plots']['pr_curve']),
            use_container_width=True
        )

def show():
    """Display analysis results"""
    if 'analysis_results' not in st.session_state:
        st.warning("No analysis results available. Please run analysis first.")
        return
    
    results = st.session_state.analysis_results
    
    if not results.get('success'):
        st.error(f"Analysis failed: {results.get('error', 'Unknown error')}")
        return
    
    # Get metrics and feature importance
    metrics = results['metrics']
    feature_importance = results['feature_importance']
    
    # Add download button for full results
    st.download_button(
        "Download Full Results",
        data=json.dumps(results, indent=2),
        file_name="analysis_results.json",
        mime="application/json"
    )
    
    # Show each section
    show_performance_metrics(metrics)
    show_feature_importance(feature_importance)
    show_response_analysis(metrics)
    show_model_plots(metrics)
    
    # Model details in expander
    with st.expander("Model Details"):
        st.write("#### Model Configuration")
        st.json(metrics['variable_config'])
        
        st.write("#### Model Coefficients")
        coef_df = pd.DataFrame({
            'Feature': metrics['model_details']['features'],
            'Coefficient': metrics['model_details']['coefficients']
        })
        st.dataframe(coef_df, use_container_width=True)
        
        st.write(f"Intercept: {format_number(metrics['model_details']['intercept'])}")

if __name__ == "__main__":
    show()

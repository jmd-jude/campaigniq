import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

def generate_scoring_rules(
    df: pd.DataFrame,
    model_coefficients: np.ndarray,
    feature_names: List[str],
    config: Dict,
    base_score: int = 1000,
    scale_factor: int = 1000
) -> List[Dict]:
    """
    Generate intuitive scoring rules from model coefficients.
    
    Args:
        df: Input DataFrame with original data
        model_coefficients: Coefficients from trained model
        feature_names: Names of features used in model
        config: Variable configuration (types, etc.)
        base_score: Starting score (default 1000)
        scale_factor: Scale factor for coefficients (default 1000)
    
    Returns:
        List of scoring rules with conditions and point adjustments
    """
    rules = []
    
    # Start with base score rule
    rules.append({
        'variable': 'BASE',
        'condition': 'always',
        'adjustment': base_score,
        'description': 'Start with base score'
    })
    
    # Process each feature
    for feature_idx, feature_name in enumerate(feature_names):
        coefficient = model_coefficients[feature_idx]
        
        # Skip very weak effects
        if abs(coefficient) < 0.01:
            continue
            
        # Get variable details
        var_base = feature_name.split('_')[0]  # Handle one-hot encoded names
        var_config = config['variable_details'].get(var_base, {})
        var_type = var_config.get('type', 'categorical')
        
        # Calculate score adjustment
        adjustment = int(coefficient * scale_factor)
        
        if var_type == 'numerical':
            # For numeric variables, use actual value thresholds
            if pd.notna(df[feature_name]).any():  # Check if column exists and has values
                # Get range from config or data
                var_range = var_config.get('range', {})
                min_val = var_range.get('min', df[feature_name].min())
                max_val = var_range.get('max', df[feature_name].max())
                
                # Create threshold at 70% of range for high values
                high_threshold = min_val + 0.7 * (max_val - min_val)
                high_adj = int(adjustment * 0.7)  # 70% of full adjustment
                
                rules.append({
                    'variable': feature_name,
                    'condition': f'> {high_threshold:.2f}',
                    'threshold': high_threshold,
                    'adjustment': high_adj,
                    'description': f'If {var_base} is above {high_threshold:.2f}'
                })
                
                # Create threshold at 30% of range for medium values
                med_threshold = min_val + 0.3 * (max_val - min_val)
                med_adj = int(adjustment * 0.3)  # 30% of full adjustment
                
                rules.append({
                    'variable': feature_name,
                    'condition': f'> {med_threshold:.2f}',
                    'threshold': med_threshold,
                    'adjustment': med_adj,
                    'description': f'If {var_base} is above {med_threshold:.2f}'
                })
                    
        elif '_' in feature_name:  # One-hot encoded categorical
            # Extract category value from feature name
            category = '_'.join(feature_name.split('_')[1:])
            
            rules.append({
                'variable': feature_name,  # Use full name for matching
                'condition': 'present',
                'adjustment': adjustment,
                'description': f'If {var_base} is {category}'
            })
            
        else:  # Original categorical
            rules.append({
                'variable': feature_name,
                'condition': 'present',
                'adjustment': adjustment,
                'description': f'If {feature_name} is present'
            })
    
    return rules

def apply_scoring_rules(
    df: pd.DataFrame,
    rules: List[Dict]
) -> pd.Series:
    """
    Apply scoring rules to generate scores for each record.
    
    Args:
        df: Input DataFrame
        rules: List of scoring rules
        
    Returns:
        Series of scores
    """
    # Start with base score
    base_rule = next(rule for rule in rules if rule['variable'] == 'BASE')
    scores = pd.Series([base_rule['adjustment']] * len(df))
    
    # Apply each rule
    for rule in rules:
        if rule['variable'] == 'BASE':
            continue
            
        variable = rule['variable']
        condition = rule['condition']
        adjustment = rule['adjustment']
        
        if variable not in df.columns:
            continue
            
        # Handle different types of rules
        if condition.startswith('>'):  # Numeric threshold
            threshold = rule['threshold']
            mask = df[variable] > threshold
        elif condition == 'present':  # One-hot encoded or binary
            if df[variable].dtype in ['float64', 'int64']:
                mask = df[variable] == 1
            else:
                mask = df[variable].notna()
        else:
            continue
                
        # Apply adjustment where rule matches
        scores[mask] += adjustment
    
    return scores

def get_score_ranges(scores: pd.Series) -> pd.DataFrame:
    """
    Generate meaningful score ranges and their characteristics.
    
    Args:
        scores: Series of scores
        
    Returns:
        DataFrame with score ranges and their properties
    """
    # Create ranges based on actual score distribution
    min_score = scores.min()
    max_score = scores.max()
    range_size = (max_score - min_score) / 5  # 5 ranges
    
    bins = [
        min_score - 1,  # Start slightly below min
        min_score + range_size,
        min_score + 2 * range_size,
        min_score + 3 * range_size,
        min_score + 4 * range_size,
        max_score + 1  # End slightly above max
    ]
    labels = ['Very Low', 'Low', 'Medium', 'High', 'Very High']
    
    score_ranges = pd.cut(scores, bins=bins, labels=labels)
    
    # Calculate range statistics
    range_stats = pd.DataFrame({
        'count': score_ranges.value_counts(),
        'min_score': scores.groupby(score_ranges).min(),
        'max_score': scores.groupby(score_ranges).max(),
        'avg_score': scores.groupby(score_ranges).mean()
    }).round(1)
    
    # Add percentages
    range_stats['percentage'] = (range_stats['count'] / len(scores) * 100).round(1)
    
    return range_stats

def format_rule_description(rule: Dict) -> str:
    """Format a scoring rule into a readable description."""
    if rule['variable'] == 'BASE':
        return f"Start with {rule['adjustment']} points"
        
    direction = 'Add' if rule['adjustment'] > 0 else 'Subtract'
    points = abs(rule['adjustment'])
    
    return f"{rule['description']}, {direction} {points} points"

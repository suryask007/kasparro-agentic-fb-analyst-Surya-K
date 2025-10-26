import pandas as pd
import re
from src.orchestrator.graph_state import AgentState
from typing import Dict, Any, List, Optional

class EvaluatorAgent:
    def __init__(self, config: dict):
        self.config = config
        self.min_confidence = config["analysis"]["min_confidence_threshold"]

    def evaluate_node(self, state: AgentState) -> AgentState:
        """
        Quantitatively validates each hypothesis against the full dataset.
        """
        print("---  EXECUTING EVALUATOR AGENT ---")
        state["log"].append("Evaluator Agent: Validating hypotheses.")
        
        df = state["full_data"]
        hypotheses: List[Dict[str, Any]] = state["hypotheses"]
        validated_insights = []
        
        if df.empty:
            print("Evaluator Agent: No data found, skipping evaluation.")
            return state
            
        # --- 1. Define Time Periods (same logic as DataAgent) ---
        max_date = df['date'].max()
        current_period_end = max_date
        current_period_start = max_date - pd.Timedelta(days=6)
        previous_period_end = current_period_start - pd.Timedelta(days=1)
        previous_period_start = previous_period_end - pd.Timedelta(days=6)

        df_current = df[
            (df['date'] >= current_period_start) & (df['date'] <= current_period_end)
        ]
        df_previous = df[
            (df['date'] >= previous_period_start) & (df['date'] <= previous_period_end)
        ]

        # --- 2. Loop through and validate each hypothesis ---
        for hypo in hypotheses:
            hypothesis_text = hypo["hypothesis"].lower()
            print(f"Evaluator: Checking hypothesis: \"{hypo['hypothesis']}\"")
            
            # Reset confidence and evidence
            hypo['confidence'] = 0.1  # Default to low confidence
            hypo['evidence'] = "NOT VALIDATED"
            
            try:
                # --- 3. Routing Logic ---
                # Route to the correct validation function based on keywords
                
                # Check for campaign ROAS drop
                if "campaign" in hypothesis_text and "roas" in hypothesis_text:
                    # Try to extract campaign name
                    name = self._extract_entity(hypo['hypothesis'], df['campaign_name'].unique())
                    if name:
                        hypo = self._validate_campaign_roas_drop(hypo, name, df_current, df_previous)
                    else:
                        hypo['evidence'] = "Could not identify a valid campaign name in hypothesis."

                # Check for audience CTR drop (fatigue)
                elif ("audience" in hypothesis_text and "ctr" in hypothesis_text) or "fatigue" in hypothesis_text:
                    # Try to extract audience name
                    name = self._extract_entity(hypo['hypothesis'], df['audience_type'].unique())
                    if name:
                        hypo = self._validate_audience_ctr_drop(hypo, name, df_current, df_previous)
                    else:
                        hypo['evidence'] = "Could not identify a valid audience name in hypothesis."
                
                else:
                    hypo['evidence'] = "No specific validation logic found for this hypothesis type."
                    print(f"  -> SKIPPED: No validation logic.")

            except Exception as e:
                print(f"  -> ERROR validating hypothesis: {e}")
                hypo['evidence'] = f"Error during validation: {e}"

            # --- 4. Store if validated ---
            if hypo['confidence'] >= self.min_confidence:
                validated_insights.append(hypo)
                print(f"  -> VALIDATED: {hypo['evidence']}")
            else:
                print(f"  -> REJECTED: {hypo['evidence']}")


        state["validated_insights"] = validated_insights
        print(f"Evaluator Agent: Validated {len(validated_insights)} insights.")
        return state

    def _extract_entity(self, text: str, entity_list: List[str]) -> Optional[str]:
        """Finds the first matching entity from a list in the text."""
        for entity in entity_list:
            if re.search(re.escape(entity), text, re.IGNORECASE):
                return entity
        return None

    def _calculate_kpis_for_segment(self, df: pd.DataFrame) -> pd.Series:
        """Aggregates KPIs for a pre-filtered dataframe."""
        if df.empty:
            return pd.Series({'spend': 0, 'revenue': 0, 'clicks': 0, 'impressions': 0, 'roas': 0, 'ctr': 0})
        
        spend = df['spend'].sum()
        revenue = df['revenue'].sum()
        clicks = df['clicks'].sum()
        impressions = df['impressions'].sum()
        
        roas = revenue / spend if spend > 0 else 0
        ctr = clicks / impressions if impressions > 0 else 0
        
        return pd.Series({
            'spend': spend, 'revenue': revenue, 'clicks': clicks, 
            'impressions': impressions, 'roas': roas, 'ctr': ctr
        })

    def _validate_campaign_roas_drop(self, hypo: Dict[str, Any], campaign_name: str, 
                                     df_current: pd.DataFrame, df_previous: pd.DataFrame) -> Dict[str, Any]:
        """Checks for a significant ROAS drop for a specific campaign."""
        
        kpi_current = self._calculate_kpis_for_segment(df_current[df_current['campaign_name'] == campaign_name])
        kpi_previous = self._calculate_kpis_for_segment(df_previous[df_previous['campaign_name'] == campaign_name])
        
        # Check 1: Must have meaningful spend
        if kpi_current['spend'] < 50:
            hypo['evidence'] = f"REJECTED: Campaign '{campaign_name}' has insufficient spend (${kpi_current['spend']:.0f}) in the current period."
            return hypo
            
        # Check 2: Previous ROAS must be valid
        if kpi_previous['roas'] == 0:
            hypo['evidence'] = f"REJECTED: Campaign '{campaign_name}' had 0 ROAS in the previous period."
            return hypo
        
        # Check 3: ROAS must have dropped significantly
        roas_change_pct = (kpi_current['roas'] - kpi_previous['roas']) / kpi_previous['roas']
        
        if roas_change_pct < -0.20: # At least a 20% drop
            hypo['confidence'] = 0.9
            hypo['evidence'] = (
                f"CONFIRMED: '{campaign_name}' ROAS dropped by **{roas_change_pct:.1%}** "
                f"(from {kpi_previous['roas']:.2f} to {kpi_current['roas']:.2f})."
            )
        else:
            hypo['evidence'] = (
                f"REJECTED: '{campaign_name}' ROAS change ({roas_change_pct:.1%}) was not a significant drop. "
                f"(from {kpi_previous['roas']:.2f} to {kpi_current['roas']:.2f})."
            )
        return hypo

    def _validate_audience_ctr_drop(self, hypo: Dict[str, Any], audience_name: str, 
                                    df_current: pd.DataFrame, df_previous: pd.DataFrame) -> Dict[str, Any]:
        """Checks for a significant CTR drop (fatigue) for a specific audience."""
        
        kpi_current = self._calculate_kpis_for_segment(df_current[df_current['audience_type'] == audience_name])
        kpi_previous = self._calculate_kpis_for_segment(df_previous[df_previous['audience_type'] == audience_name])

        # Check 1: Must have meaningful impressions
        if kpi_current['impressions'] < 1000:
            hypo['evidence'] = f"REJECTED: Audience '{audience_name}' has insufficient impressions ({kpi_current['impressions']:.0f}) in the current period."
            return hypo

        # Check 2: Previous CTR must be valid
        if kpi_previous['ctr'] == 0:
            hypo['evidence'] = f"REJECTED: Audience '{audience_name}' had 0 CTR in the previous period."
            return hypo
            
        # Check 3: CTR must have dropped significantly
        ctr_change_pct = (kpi_current['ctr'] - kpi_previous['ctr']) / kpi_previous['ctr']
        
        if ctr_change_pct < -0.15: # At least a 15% drop
            hypo['confidence'] = 0.9
            hypo['evidence'] = (
                f"CONFIRMED: Audience '{audience_name}' CTR dropped by **{ctr_change_pct:.1%}** "
                f"(from {kpi_previous['ctr']:.4f} to {kpi_current['ctr']:.4f}), indicating fatigue."
            )
        else:
            hypo['evidence'] = (
                f"REJECTED: Audience '{audience_name}' CTR change ({ctr_change_pct:.1%}) was not a significant drop. "
                f"(from {kpi_previous['ctr']:.4f} to {kpi_current['ctr']:.4f})."
            )
        return hypo
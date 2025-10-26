import pandas as pd
from src.orchestrator.graph_state import AgentState
from typing import Dict, Any

class DataAgent:
    def __init__(self, config: dict):
        self.config = config
        self.data_path = (
            config["paths"]["sample_data"]
            if config["system"]["use_sample_data"]
            else config["paths"]["full_data"]
        )
        self.low_ctr_top_n = config["analysis"].get("creative_gen_top_n", 3)

    def load_data_node(self, state: AgentState) -> AgentState:
        """Loads the dataset."""
        print("---  EXECUTING DATA AGENT (LOAD) ---")
        state["log"].append("Data Agent: Loading data.")
        try:
            df = pd.read_csv(self.data_path)
            # --- Critical Preprocessing ---
            df['date'] = pd.to_datetime(df['date'])
            # Ensure numeric types are correct
            numeric_cols = ['spend', 'impressions', 'clicks', 'purchases', 'revenue']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            df = df.fillna(0) # Simple fillna for this task
            
            # Recalculate metrics in case they are missing or wrong
            df['roas'] = df.apply(lambda row: row['revenue'] / row['spend'] if row['spend'] > 0 else 0, axis=1)
            df['ctr'] = df.apply(lambda row: row['clicks'] / row['impressions'] if row['impressions'] > 0 else 0, axis=1)
            
            state["full_data"] = df
            print(f"Data Agent: Loaded {len(df)} rows from {self.data_path}.")
        except Exception as e:
            print(f"Data Agent: Error loading data: {e}")
            state["log"].append(f"Data Agent: Error loading data: {e}")
        return state

    def summarize_data_node(self, state: AgentState) -> AgentState:
        """
        Summarizes data based on the plan.
        This is where the core pandas logic lives.
        """
        print("---  EXECUTING DATA AGENT (SUMMARIZE) ---")
        state["log"].append("Data Agent: Summarizing data for insights.")
        df = state["full_data"]
        query = state["user_query"]
        
        # --- 1. Define Time Periods ---
        # We'll hardcode "last 7 days" analysis based on the sample query.
        # A more complex agent would parse the query (e.g., "last 30 days").
        
        # Ensure data is sorted by date
        df = df.sort_values('date')
        
        if df.empty:
            state["data_summary"] = "Error: No data loaded."
            return state

        max_date = df['date'].max()
        
        # Define current and previous periods
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

        if df_current.empty:
            state["data_summary"] = f"Error: No data found for the current period ({current_period_start.date()} to {current_period_end.date()})."
            return state
        if df_previous.empty:
            state["data_summary"] = f"Error: No data found for the previous period ({previous_period_start.date()} to {previous_period_end.date()}) to compare against."
            return state

        # --- 2. Calculate KPIs (Overall) ---
        kpis_current = self._calculate_kpis(df_current)
        kpis_previous = self._calculate_kpis(df_previous)

        # --- 3. Calculate Segmented KPIs (Campaigns & Audiences) ---
        
        # By Campaign
        campaign_kpis_current = df_current.groupby('campaign_name').apply(self._calculate_kpis)
        campaign_kpis_previous = df_previous.groupby('campaign_name').apply(self._calculate_kpis)
        campaign_comparison = campaign_kpis_current.join(
            campaign_kpis_previous, lsuffix='_current', rsuffix='_previous', how='outer'
        ).fillna(0)
        campaign_comparison['roas_change_pct'] = (
            (campaign_comparison['roas_current'] - campaign_comparison['roas_previous']) / 
             campaign_comparison['roas_previous']
        )
        # Filter for campaigns with meaningful spend
        campaign_comparison = campaign_comparison[campaign_comparison['spend_current'] > 50]
        worst_campaigns = campaign_comparison.sort_values('roas_change_pct').head(3)

        # By Audience
        audience_kpis_current = df_current.groupby('audience_type').apply(self._calculate_kpis)
        audience_kpis_previous = df_previous.groupby('audience_type').apply(self._calculate_kpis)
        audience_comparison = audience_kpis_current.join(
            audience_kpis_previous, lsuffix='_current', rsuffix='_previous', how='outer'
        ).fillna(0)
        audience_comparison['ctr_change_pct'] = (
            (audience_comparison['ctr_current'] - audience_comparison['ctr_previous']) / 
             audience_comparison['ctr_previous']
        )
        # Filter for audiences with meaningful impressions
        audience_comparison = audience_comparison[audience_comparison['impressions_current'] > 1000]
        worst_audiences = audience_comparison.sort_values('ctr_change_pct').head(3)
        
        # --- 4. Identify Low-CTR Campaigns for Creative Gen ---
        # This is a separate task: find lowest CTR in *current* period 
        campaign_ctr_current = campaign_kpis_current.sort_values('ctr')
        # Filter for campaigns with enough impressions to be significant
        significant_campaigns = campaign_ctr_current[campaign_ctr_current['impressions'] > 1000]
        low_ctr_campaigns_list = significant_campaigns.head(self.low_ctr_top_n).index.tolist()
        
        state["low_ctr_campaigns"] = low_ctr_campaigns_list

        # --- 5. Format the Text Summary ---
        summary_lines = []
        summary_lines.append(f"Analysis for query: '{query}'")
        summary_lines.append(f"Period Analyzed: {current_period_start.date()} to {current_period_end.date()} (vs. {previous_period_start.date()} to {previous_period_end.date()})\n")

        summary_lines.append("--- Overall Performance ---")
        summary_lines.append(self._format_kpi_comparison(kpis_current, kpis_previous))

        summary_lines.append("\n--- Top Campaign ROAS Decliners ---")
        if worst_campaigns.empty:
            summary_lines.append("No significant campaign ROAS declines found.")
        else:
            for name, row in worst_campaigns.iterrows():
                summary_lines.append(
                    f"- **{name}**: ROAS dropped by **{row['roas_change_pct']:.1%}** "
                    f"(from {row['roas_previous']:.2f} to {row['roas_current']:.2f}). "
                    f"Spend: ${row['spend_current']:.0f}. "
                    f"CTR: {row['ctr_current']:.4f}."
                )

        summary_lines.append("\n--- Top Audience CTR Decliners (Potential Fatigue) ---")
        if worst_audiences.empty:
            summary_lines.append("No significant audience CTR declines found.")
        else:
            for name, row in worst_audiences.iterrows():
                summary_lines.append(
                    f"- **{name}**: CTR dropped by **{row['ctr_change_pct']:.1%}** "
                    f"(from {row['ctr_previous']:.4f} to {row['ctr_current']:.4f}). "
                    f"Spend: ${row['spend_current']:.0f}. "
                    f"ROAS: {row['roas_current']:.2f}."
                )

        summary_lines.append(f"\n--- Low-CTR Campaigns Identified for Creative Review ---")
        summary_lines.append(f"{', '.join(low_ctr_campaigns_list)}")

        final_summary = "\n".join(summary_lines)
        state["data_summary"] = final_summary
        
        print("Data Agent: Summary generated.")
        print(final_summary)
        
        return state

    def _calculate_kpis(self, df: pd.DataFrame) -> pd.Series:
        """Helper function to aggregate KPIs from a dataframe."""
        if df.empty:
            return pd.Series(index=self._kpi_names(), data=[0]*len(self._kpi_names()))

        spend = df['spend'].sum()
        revenue = df['revenue'].sum()
        purchases = df['purchases'].sum()
        clicks = df['clicks'].sum()
        impressions = df['impressions'].sum()
        
        roas = revenue / spend if spend > 0 else 0
        ctr = clicks / impressions if impressions > 0 else 0
        cpc = spend / clicks if clicks > 0 else 0
        cpa = spend / purchases if purchases > 0 else 0
        cr = purchases / clicks if clicks > 0 else 0 # Conversion Rate (Purchases / Clicks)
        
        return pd.Series({
            'spend': spend,
            'revenue': revenue,
            'purchases': purchases,
            'clicks': clicks,
            'impressions': impressions,
            'roas': roas,
            'ctr': ctr,
            'cpc': cpc,
            'cpa': cpa,
            'cr': cr
        })

    def _kpi_names(self) -> list:
        """Helper for empty series creation."""
        return ['spend', 'revenue', 'purchases', 'clicks', 'impressions',
                'roas', 'ctr', 'cpc', 'cpa', 'cr']

    def _format_kpi_comparison(self, current: pd.Series, previous: pd.Series) -> str:
        """Helper to create a summary string for a single set of KPIs."""
        
        def pct_change(c, p):
            if p == 0:
                return " (N/A)"
            change = (c - p) / p
            return f" ({change:+.1%})"

        lines = [
            f"- **ROAS**:    {current['roas']:.2f} (vs {previous['roas']:.2f}){pct_change(current['roas'], previous['roas'])}",
            f"- **Revenue**: ${current['revenue']:,.0f} (vs ${previous['revenue']:,.0f}){pct_change(current['revenue'], previous['revenue'])}",
            f"- **Spend**:   ${current['spend']:,.0f} (vs ${previous['spend']:,.0f}){pct_change(current['spend'], previous['spend'])}",
            f"- **CTR**:     {current['ctr']:.4f} (vs {previous['ctr']:.4f}){pct_change(current['ctr'], previous['ctr'])}",
            f"- **CR (Conv. Rate)**: {current['cr']:.4f} (vs {previous['cr']:.4f}){pct_change(current['cr'], previous['cr'])}",
        ]
        return "\n".join(lines)
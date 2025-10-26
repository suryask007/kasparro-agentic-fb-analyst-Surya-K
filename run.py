import sys
import yaml
import os
import random
import numpy as np
from typing import Dict, Any

from src.orchestrator.graph import build_agent_graph, save_outputs


def load_config() -> Dict[str, Any]:
    """Loads config.yaml."""
    try:
        with open("config/config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("Error: config/config.yaml not found.")
        sys.exit(1)

def set_seeds(seed: int):
    """Sets random seeds for reproducibility[cite: 56]."""
    os.environ['PYTHONHASHSEED'] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    # Add other library seeds (e.g., torch) if needed

def main():
    # Get user query from CLI
    if len(sys.argv) < 2:
        print("Usage: python src/run.py '<your_query>'")
        print("Example: python src/run.py 'Analyze ROAS drop in last 7 days'")
        sys.exit(1)
    
    user_query = sys.argv[1]
    print(f"---  STARTING AGENTIC FB ANALYST ---")
    print(f"Query: {user_query}")
    
    # Load config and set seeds
    config = load_config()
    set_seeds(config["system"]["random_seed"])

    # Create directories if they don't exist
    os.makedirs(config["paths"]["reports"], exist_ok=True)
    os.makedirs(config["paths"]["logs"], exist_ok=True)

    # Build the agentic graph
    app = build_agent_graph(config)
    
    # Define the initial state
    initial_state = {
        "user_query": user_query,
        "plan": [],
        "full_data": None,
        "data_summary": None,
        "hypotheses": [],
        "validated_insights": [],
        "low_ctr_campaigns": [],
        "creative_recommendations": [],
        "log": []
    }
    
    # Run the graph
    print("---  EXECUTING AGENT GRAPH ---")
    final_state = app.invoke(initial_state)
    
    # Save the final outputs
    save_outputs(final_state, config)
    
    print("---  ANALYSIS COMPLETE ---")

if __name__ == "__main__":
    main()
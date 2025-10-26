import json
import yaml
from langgraph.graph import StateGraph, END
from typing import Literal

from src.orchestrator.graph_state import AgentState
from src.agents.planner_agent import get_planner_agent
from src.agents.data_agent import DataAgent
from src.agents.insight_agent import get_insight_agent
from src.agents.evaluator_agent import EvaluatorAgent
from src.agents.creative_agent import get_creative_agent

def build_agent_graph(config: dict):
    """
    Builds the main agentic graph.
    """
    # Initialize agents
    planner_agent = get_planner_agent(config)
    data_agent = DataAgent(config)
    insight_agent = get_insight_agent(config)
    evaluator_agent = EvaluatorAgent(config)
    creative_agent = get_creative_agent(config)

    # Define the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("planner", planner_agent)
    workflow.add_node("load_data", data_agent.load_data_node)
    workflow.add_node("summarize_data", data_agent.summarize_data_node)
    workflow.add_node("generate_insights", insight_agent)
    workflow.add_node("evaluate_insights", evaluator_agent.evaluate_node)
    workflow.add_node("generate_creatives", creative_agent)

    # Set entry point
    workflow.set_entry_point("planner")

    # Add edges
    workflow.add_edge("planner", "load_data")
    workflow.add_edge("load_data", "summarize_data")
    workflow.add_edge("summarize_data", "generate_insights")
    
    # This is the evaluation loop 
    workflow.add_edge("generate_insights", "evaluate_insights")
    
    workflow.add_conditional_edges(
        "evaluate_insights",
        should_continue, # Decision function
        {
            "generate_creatives": "generate_creatives",
            "log_and_finish": END 
        }
    )
    
    workflow.add_edge("generate_creatives", END)

    # Compile the graph
    app = workflow.compile()
    
    # Save a diagram of the graph
    try:
        app.get_graph().draw_mermaid_png(output_file_path="reports/agent_graph.png")
    except Exception as e:
        print(f"Could not draw graph: {e}. Make sure 'pygraphviz' is installed.")

    return app

def should_continue(state: AgentState) -> Literal["generate_creatives", "log_and_finish"]:
    """
    Decision node: Checks if insights were validated.
    If yes -> proceed to creative generation.
    If no -> end the run (or, in a more complex setup, loop back to insights).
    """
    print("---  EXECUTING DECISION NODE ---")
    if state["validated_insights"]:
        print("Decision: Validated insights found. Proceeding to creative generation.")
        return "generate_creatives"
    else:
        print("Decision: No validated insights. Finishing run.")
        return "log_and_finish"

def save_outputs(state: dict, config: dict):
    """
    Saves the final reports as JSON and Markdown.
    """
    print("---  SAVING OUTPUTS ---")
    report_path = config["paths"]["reports"]
    
    # Save insights.json 
    with open(f"{report_path}insights.json", "w") as f:
        json.dump(state["validated_insights"], f, indent=2)
        
    # Save creatives.json 
    with open(f"{report_path}creatives.json", "w") as f:
        json.dump(state["creative_recommendations"], f, indent=2)
        
    # Save report.md 
    with open(f"{report_path}report.md", "w") as f:
        f.write("# Agentic Facebook Ads Analysis Report\n\n")
        f.write(f"**Query:** {state['user_query']}\n\n")
        
        f.write("## 1. Validated Insights\n\n")
        if not state["validated_insights"]:
            f.write("No significant insights were quantitatively validated.\n\n")
        else:
            for insight in state["validated_insights"]:
                f.write(f"-   **Hypothesis:** {insight['hypothesis']}\n")
                f.write(f"    -   **Confidence:** {insight['confidence'] * 100:.0f}%\n")
                f.write(f"    -   **Evidence:** {insight['evidence']}\n\n")

        f.write("## 2. Creative Recommendations\n\n")
        if not state["creative_recommendations"]:
            f.write("No creative recommendations were generated.\n\n")
        else:
            for rec in state["creative_recommendations"]:
                f.write(f"### For Campaign: {rec['campaign_name']}\n\n")
                f.write("**New Headlines:**\n")
                for h in rec['new_headlines']:
                    f.write(f"-   {h}\n")
                f.write("\n**New Messages:**\n")
                for m in rec['new_messages']:
                    f.write(f"-   {m}\n")
                f.write("\n")
                
    # Save logs
    with open(f"{config['paths']['logs']}run_log.json", "w") as f:
        # Need to handle non-serializable items like DataFrames
        log_state = {k: v for k, v in state.items() if k not in ['full_data']}
        json.dump(log_state, f, indent=2, default=str)
        
    print(f"Outputs saved to {report_path}")
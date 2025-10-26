from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel,Field
from typing import List

from src.orchestrator.graph_state import AgentState
from src.utils.llm import get_llm

class Plan(BaseModel):
    """The multi-step plan to diagnose ad performance."""
    steps: List[str] = Field(
        description="A list of clear, sequential steps to analyze the data and generate insights."
    )

def get_planner_agent(config: dict):
    """Returns the planner agent node."""
    
    llm = get_llm(
        model_name=config["llm"]["model_name"],
        temperature=config["llm"]["temperature"]
    ).with_structured_output(Plan)
    
    prompt_template = ChatPromptTemplate.from_template(
        _load_prompt_template(config["paths"]["prompts"], "planner_prompt.md")
    )
    
    planner_chain = prompt_template | llm
    
    def planner_node(state: AgentState) -> AgentState:
        """Generates the initial plan."""
        print("---  EXECUTING PLANNER AGENT ---")
        state["log"].append("Planner: Generating plan.")
        
        plan_output = planner_chain.invoke({"query": state["user_query"]})
        print("plan_output------:",plan_output)
        state["plan"] = plan_output.steps
        print(f"Planner generated plan: {plan_output.steps}")
        return state

    return planner_node

def _load_prompt_template(path: str, filename: str) -> str:
    """Helper to load prompt templates from files."""
    try:
        with open(f"{path}{filename}", "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {path}{filename}")
        return "" # Should handle this more gracefully
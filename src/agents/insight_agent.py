from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel,Field
from typing import List, Dict, Any

from src.orchestrator.graph_state import AgentState
from src.utils.llm import get_llm

class Hypothesis(BaseModel):
    """A single hypothesis explaining a performance change."""
    hypothesis: str = Field(description="The hypothesis statement.")
    confidence: float = Field(
        description="Initial confidence score (0.0-1.0) based on summary."
    )
    data_needed_for_validation: str = Field(
        description="What data or query is needed to validate this?"
    )

class HypothesisList(BaseModel):
    """A list of hypotheses."""
    hypotheses: List[Hypothesis]

def get_insight_agent(config: dict):
    """Returns the insight agent node."""
    
    llm = get_llm(
        model_name=config["llm"]["model_name"],
        temperature=config["llm"]["temperature"]
    ).with_structured_output(HypothesisList)
    
    prompt_template = ChatPromptTemplate.from_template(
        _load_prompt_template(config["paths"]["prompts"], "insight_prompt.md")
    )
    
    insight_chain = prompt_template | llm
    
    def insight_node(state: AgentState) -> AgentState:
        """Generates hypotheses from data summary."""
        print("--- EXECUTING INSIGHT AGENT ---")
        state["log"].append("Insight Agent: Generating hypotheses.")
        
        response = insight_chain.invoke({
            "query": state["user_query"],
            "data_summary": state["data_summary"]
        })
        print("response------->",response)
        hypotheses_list = [h.dict() for h in response.hypotheses]
        state["hypotheses"] = hypotheses_list
        print(f"Insight Agent: Generated {len(hypotheses_list)} hypotheses.")
        
        return state

    return insight_node

def _load_prompt_template(path: str, filename: str) -> str:
    """Helper to load prompt templates from files."""
    try:
        with open(f"{path}{filename}", "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {path}{filename}")
        return ""
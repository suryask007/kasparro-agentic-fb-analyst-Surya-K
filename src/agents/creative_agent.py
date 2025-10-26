from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from typing import List, Dict, Any
import pandas as pd

from src.orchestrator.graph_state import AgentState
from src.utils.llm import get_llm

class CreativeSet(BaseModel):
    """New creative recommendations for a single campaign."""
    campaign_name: str
    new_headlines: List[str]
    new_messages: List[str]
    new_ctas: List[str]

class CreativeList(BaseModel):
    """List of creative recommendations."""
    recommendations: List[CreativeSet]

def get_creative_agent(config: dict):
    """Returns the creative improvement generator node."""
    
    llm = get_llm(
        model_name=config["llm"]["model_name"],
        temperature=0.7 # Higher temp for creativity
    ).with_structured_output(CreativeList)
    
    prompt_template = ChatPromptTemplate.from_template(
        _load_prompt_template(config["paths"]["prompts"], "creative_prompt.md")
    )
    
    creative_chain = prompt_template | llm
    
    def creative_node(state: AgentState) -> AgentState:
        """Generates new creative ideas."""
        print("---  EXECUTING CREATIVE AGENT ---")
        state["log"].append("Creative Agent: Generating recommendations.")
        
        low_ctr_campaigns = state["low_ctr_campaigns"]
        if not low_ctr_campaigns:
            print("Creative Agent: No low-CTR campaigns identified.")
            return state
            
        # Get existing creative messages for context [cite: 8]
        df = state["full_data"]
        existing_creatives = df[df['campaign_name'].isin(low_ctr_campaigns)][
            ['campaign_name', 'creative_message', 'ctr']
        ].drop_duplicates().to_string()

        response = creative_chain.invoke({
            "insights": str(state["validated_insights"]),
            "campaign_list": str(low_ctr_campaigns),
            "existing_creatives": existing_creatives
        })
        
        recommendations = [r.dict() for r in response.recommendations]
        state["creative_recommendations"] = recommendations
        print(f"Creative Agent: Generated {len(recommendations)} creative sets.")
        
        return state

    return creative_node

def _load_prompt_template(path: str, filename: str) -> str:
    """Helper to load prompt templates from files."""
    try:
        with open(f"{path}{filename}", "r") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {path}{filename}")
        return ""
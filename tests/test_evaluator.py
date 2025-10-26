import pandas as pd
import pytest
from src.agents.evaluator_agent import EvaluatorAgent
from src.orchestrator.graph_state import AgentState

# Sample config for testing
@pytest.fixture
def test_config():
    return {
        "analysis": {"min_confidence_threshold": 0.7},
        "llm": {}, # Not needed for this test
    }

# Sample data for testing
@pytest.fixture
def sample_data():
    data = {
        'date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
        'campaign_name': ['Campaign_A', 'Campaign_A', 'Campaign_A'],
        'audience_type': ['Audience_X', 'Audience_X', 'Audience_X'],
        'roas': [5.0, 3.0, 1.0],
        'ctr': [0.05, 0.03, 0.01]
    }
    return pd.DataFrame(data)

def test_evaluator_validates_hypothesis(test_config, sample_data):
    """
    Tests if the evaluator correctly validates a true hypothesis.

    This test will FAIL until you implement the *actual*
    pandas logic inside `evaluator_agent.py`.
    
    Once you do, update this test to match that logic.
    """
    
    # Arrange
    evaluator = EvaluatorAgent(test_config)
    initial_state = AgentState(
        full_data=sample_data,
        hypotheses=[
            {
                "hypothesis": "ROAS for Campaign_A decreased due to CTR drop.",
                "confidence": 0.5, # Initial confidence
                "data_needed_for_validation": "Check ROAS and CTR trend for Campaign_A"
            }
        ],
        # ... other state fields ...
        user_query="", plan=[], data_summary=None, validated_insights=[],
        low_ctr_campaigns=[], creative_recommendations=[], log=[]
    )
    
    # Act
    result_state = evaluator.evaluate_node(initial_state)
    
    # Assert
    # This assertion will fail until you implement the real logic
    assert len(result_state["validated_insights"]) == 1
    assert result_state["validated_insights"][0]["confidence"] >= 0.7
    assert "Confirmed" in result_state["validated_insights"][0]["evidence"]

def test_evaluator_rejects_hypothesis(test_config, sample_data):
    """
    Tests if the evaluator correctly rejects a false hypothesis.
    """
    # Arrange
    evaluator = EvaluatorAgent(test_config)
    initial_state = AgentState(
        full_data=sample_data,
        hypotheses=[
            {
                "hypothesis": "ROAS for Campaign_A *increased*.",
                "confidence": 0.5,
                "data_needed_for_validation": "Check ROAS trend for Campaign_A"
            }
        ],
        # ... other state fields ...
        user_query="", plan=[], data_summary=None, validated_insights=[],
        low_ctr_campaigns=[], creative_recommendations=[], log=[]
    )
    
    # Act
    result_state = evaluator.evaluate_node(initial_state)
    
    # Assert
    assert len(result_state["validated_insights"]) == 0
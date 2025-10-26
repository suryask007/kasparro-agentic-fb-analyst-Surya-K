# import os
# from langchain_openai import ChatOpenAI
# from dotenv import load_dotenv

# def get_llm(model_name: str, temperature: float):
#     """Initializes and returns the ChatOpenAI model."""
#     load_dotenv()
#     if not os.getenv("OPENAI_API_KEY"):
#         raise EnvironmentError("OPENAI_API_KEY not found in .env file.")
        
#     return ChatOpenAI(
#         model=model_name,
#         temperature=temperature,
#         max_retries=2,
#     )


import os
# from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

from dotenv import load_dotenv

def get_llm(model_name: str, temperature: float):
    """Initializes and returns the ChatOpenAI model."""
    load_dotenv()
    if not os.getenv("GOOGLE_API_KEY"):
        raise EnvironmentError("GOOGLE_API_KEY not found in .env file.")
        
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        max_retries=2,
    )
#llm_runnable.py
import os
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel
from dotenv import load_dotenv

class create_runnable:
    def __init__(self,
                 prompt: ChatPromptTemplate,
                 model: str = "o4-mini",
                 temperature: float = 1.0):
        load_dotenv()
        self.llm = AzureChatOpenAI(
            api_key=os.getenv("LLM_FARM_API_KEY"),
            azure_deployment=os.getenv("AZURE_DEPLOYMENT"),
            api_version=os.getenv("AZURE_API_VERSION"),
            azure_endpoint=os.getenv("AZURE_ENDPOINT"),
            temperature=temperature,
            default_headers={"genaiplatform-farm-subscription-key": os.getenv("LLM_FARM_API_KEY")}
        )
        self.prompt = prompt

    def get_runnable_with_structured_output(self, structured_output: BaseModel):
        self.llm = self.llm.with_structured_output(structured_output, method="function_calling")
        return self.prompt | self.llm  # return RunnableSequence

    def get_runnable(self):
        return self.prompt | self.llm

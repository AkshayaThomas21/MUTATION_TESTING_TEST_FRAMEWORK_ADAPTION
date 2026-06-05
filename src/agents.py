#agents.py
import os
import json
import logging
from datetime import datetime
from langchain_core.runnables import RunnableConfig

log = logging.getLogger(__name__)
from src.data_classes import Mutant, MutantGenAgentState, TestGenAgentState, EquivalentCheckAgentState
from src.utils import (
    stringify_hints,
    stringify_test_cases,
    stringify_mutants,
    stringify_mutant_list,
    stringify_feedback,
    stringify_function_dict,
    stringify_ranked_mutants
)


class MutantGenerator:
    def __init__(self, runnable_chain, prompt_template):
        self.runnable_chain = runnable_chain
        self.prompt_template = prompt_template

    def get_prompt_data(self, state: MutantGenAgentState, config: RunnableConfig):
        self.prompt_dict = {
            'code': state.function_code,
            'mutants': stringify_mutants(state.mutation_result),
            'feedback': stringify_feedback(state.feedback),
            'survived_mutants': stringify_mutant_list(state.survived_mutants),
            'killed_mutants': stringify_mutant_list(state.killed_mutants),
            'hints': stringify_hints(state.test_case_hints),
            'ratings_summary': state.ratings_summary,
            'dependency_data': stringify_function_dict(state.dependency_data),
        }

    def __call__(self, state: MutantGenAgentState, config: RunnableConfig):
        print("\n---CALLED MUTATION GENERATOR AGENT---")
        self.get_prompt_data(state, config)
        response = self.runnable_chain.invoke(self.prompt_dict)
        return {"mutation_result": response, "super_step_count": state.super_step_count + 1}


class MutantReflector:
    def __init__(self, runnable_chain):
        self.runnable_chain = runnable_chain

    def get_prompt_data(self, state: MutantGenAgentState):
        self.prompt_dict = {
            'code': state.function_code,
            'mutants': stringify_mutants(state.mutation_result),
            'hints': stringify_hints(state.test_case_hints),
        }

    def __call__(self, state: MutantGenAgentState):
        print("\n---CALLED MUTATION REFLECTOR AGENT---")
        self.get_prompt_data(state)
        response = self.runnable_chain.invoke(self.prompt_dict)

        # Merge user feedback if present
        feedback_path = os.path.join("intermediate", "user_feedback.txt")
        if os.path.exists(feedback_path):
            try:
                with open(feedback_path, "r", encoding="utf-8") as f:
                    user_fb = f.read().strip()
                if user_fb:
                    if hasattr(response, "feedback"):
                        response.feedback = (response.feedback + "\n" + user_fb).strip()
                    else:
                        response = (response + "\n" + user_fb).strip()
            except Exception as e:
                print(f"[WARNING] Could not merge user feedback: {e}")

        return {"feedback": response}


class TestcaseAnalyzer:
    def __init__(self, runnable_chain):
        context_summary_path = "intermediate/source_context.json"
        self.runnable_chain = runnable_chain
        self.context_summary_path = context_summary_path

    def get_context_summary(self):
        if os.path.exists(self.context_summary_path):
            try:
                with open(self.context_summary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("context_summary", "")
            except Exception as e:
                log.debug(f"[WARNING] Could not read context summary: {e}")
        return ""

    def get_prompt_data(self, state):
        context_summary = self.get_context_summary()
        self.prompt_dict = {
            "code": state.function_code,
            "test_cases": stringify_test_cases(state.test_case_data),
            "survived_mutants": stringify_mutant_list(state.survived_mutants),
            "killed_mutants": stringify_mutant_list(state.killed_mutants),
            "context_summary": context_summary or "No additional context provided."
        }

    def __call__(self, state):
        print("\n---CALLED TESTCASE ANALYZER AGENT---")
        self.get_prompt_data(state)
        response = self.runnable_chain.invoke(self.prompt_dict)
        return {"test_case_hints": response}


class TestcaseGenerator:
    def __init__(self, runnable_chain):
        self.runnable_chain = runnable_chain

    def get_prompt_data(self, state: TestGenAgentState):
        self.prompt_dict = {
            'code': state.function_code,
            'test_cases': stringify_test_cases(state.test_case_data),
            'survived_mutants': stringify_mutant_list(state.survived_mutants),
            'dependency_data': stringify_function_dict(state.dependency_data),
        }

    def __call__(self, state: TestGenAgentState):
        print("\n---CALLED TESTCASE GENERATOR AGENT---")
        self.get_prompt_data(state)
        response = self.runnable_chain.invoke(self.prompt_dict)
        return {"generated_test_case": response}


class EquivalentChecker:
    def __init__(self, runnable_chain, equivalent_file_path=None):
        self.runnable_chain = runnable_chain
        self.equivalent_file_path = equivalent_file_path

    def get_prompt_data(self, mutant: Mutant, state: EquivalentCheckAgentState):
        self.prompt_dict = {
            'code': state.function_code,
            'generated_mutants': stringify_mutant_list([mutant]),
            'dependency_data': stringify_function_dict(state.dependency_data),
        }

    def __call__(self, state: EquivalentCheckAgentState):
        print("\n---CALLED EQUIVALENT CHECKER AGENT---")

        mutant_list = state.generated_mutants
        filtered_mutants = []
        equivalent_mutants = []

        for mutant in mutant_list:
            self.get_prompt_data(mutant, state)
            response = self.runnable_chain.invoke(self.prompt_dict)
            if getattr(response, "is_equivalent_mutant", None) == "Not Equivalent":
                filtered_mutants.append(mutant)
            else:
                log.debug(f"Equivalent Mutant detected: {stringify_mutant_list([mutant])}")
                equivalent_mutants.append(mutant)

        if equivalent_mutants and self.equivalent_file_path:
            self.save_equivalent_mutants(state, equivalent_mutants)

        return {"filtered_mutants": filtered_mutants, "equivalent_mutants": equivalent_mutants}

    def save_equivalent_mutants(self, state: EquivalentCheckAgentState, equivalent_mutants: list):
        file_path = self.equivalent_file_path
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}

        function_name = self.extract_function_name(state.function_code)
        if function_name not in data:
            data[function_name] = []

        for mutant in equivalent_mutants:
            data[function_name].append({
                "original_code": mutant.original_code,
                "mutated_code": mutant.mutated_code,
                "mutant_category": mutant.mutant_category
            })

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print(f"Equivalent mutants for function '{function_name}' saved to: {file_path}")

    @staticmethod
    def extract_function_name(function_code: str) -> str:
        first_line = function_code.strip().splitlines()[0]
        if '(' in first_line:
            name_part = first_line.split('(')[0]
            return name_part.strip().split()[-1]
        return "unknown_function"


class MutantRanker:
    def __init__(self, structured_runnable):
        self.structured_runnable = structured_runnable

    def get_prompt_data(self, mutants):
        self.prompt_dict = {
            "mutants": mutants
        }

    def __call__(self, mutants):
        print("\n---CALLED MUTANT RANKER AGENT---")
        if len(mutants) == 0:
            log.debug("No mutants provided for ranking. Exiting ranking agent.")
            return {"ranked_mutants": []}

        self.get_prompt_data(mutants)
        structured_response = self.structured_runnable.invoke(self.prompt_dict)
        log.debug(f"Ranking completed. {len(structured_response.ranked_mutants)} mutants ranked.")
        log.debug(stringify_ranked_mutants(structured_response.ranked_mutants))
        return {"ranked_mutants": structured_response.ranked_mutants}


from dataclasses import dataclass  

class SourceAnalyzerAgent:
    def __init__(self, runnable_chain):
        self.runnable_chain = runnable_chain

    def get_prompt_data(self, state):
        self.prompt_dict = {"source_code": state.function_code}

    def __call__(self, state, config=None):
        print("--- CALLED SOURCE ANALYZER AGENT ---")
        self.get_prompt_data(state)

        if config is None or not isinstance(config, dict):
            config = {}

        ratings = config.get("configurable", {}).get("ratings")

        if ratings is None and config.get("feedback_run", False):
            ratings_path = os.path.join("intermediate", "ratings.json")
            if os.path.exists(ratings_path):
                with open(ratings_path, "r", encoding="utf-8") as f:
                    ratings = json.load(f)

        self.prompt_dict["ratings"] = ratings

        response = self.runnable_chain.invoke(self.prompt_dict)
        context_summary = getattr(response, "context_summary", str(response))

        os.makedirs("intermediate", exist_ok=True)
        with open("intermediate/source_context.json", "w", encoding="utf-8") as f:
            json.dump({"context_summary": context_summary}, f, indent=4)

        return {"context_summary": context_summary}


class HallucinationChecker:
    def __init__(self, runnable_chain, hallucination_file_path: str):
        self.runnable_chain = runnable_chain
        self.hallucination_file_path = hallucination_file_path

    def get_prompt_data(self, mutant: Mutant, state: EquivalentCheckAgentState):
        self.prompt_dict = {
            'code': state.function_code,
            'mutant': {
                "original_code": mutant.get("original_code") if isinstance(mutant, dict) else getattr(mutant, "original_code", None),
                "mutated_code": mutant.get("mutated_code") if isinstance(mutant, dict) else getattr(mutant, "mutated_code", None),
                "mutant_category": mutant.get("mutant_category") if isinstance(mutant, dict) else getattr(mutant, "mutant_category", None)
            },
            'dependency_data': stringify_function_dict(state.dependency_data),
        }

    def __call__(self, state: EquivalentCheckAgentState):
        print("\n---CALLED HALLUCINATION CHECKER AGENT---")

        mutant_list = state.generated_mutants
        filtered_mutants = []
        hallucinated_mutants = []

        for mutant in mutant_list:
            self.get_prompt_data(mutant, state)
            response = self.runnable_chain.invoke(self.prompt_dict)
            is_h = getattr(response, "is_hallucination", None)
            explanation = getattr(response, "explanation", str(response))

            if is_h == "No Hallucination":
                filtered_mutants.append(mutant)
            else:
                mutated = mutant.get("mutated_code") if isinstance(mutant, dict) else getattr(mutant, "mutated_code", None)
                original = mutant.get("original_code") if isinstance(mutant, dict) else getattr(mutant, "original_code", None)
                category = mutant.get("mutant_category") if isinstance(mutant, dict) else getattr(mutant, "mutant_category", None)
                hallucinated_mutants.append({
                    "original_code": original,
                    "mutated_code": mutated,
                    "mutant_category": category,
                    "explanation": explanation
                })
                log.debug(f"Hallucinated Mutant detected: {category} -> {explanation[:100]}")

        if hallucinated_mutants:
            self.save_hallucinated_mutants(state, hallucinated_mutants)

        return {"filtered_mutants": filtered_mutants, "hallucinations": hallucinated_mutants}

    def save_hallucinated_mutants(self, state: EquivalentCheckAgentState, hallucinated_mutants: list):
        file_path = self.hallucination_file_path
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        else:
            data = {}

        function_name = EquivalentChecker.extract_function_name(state.function_code) if hasattr(EquivalentChecker, "extract_function_name") else "unknown_function"

        if function_name not in data:
            data[function_name] = []

        data[function_name].extend(hallucinated_mutants)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        print(f"Hallucinated mutants for function '{function_name}' saved to: {file_path}")

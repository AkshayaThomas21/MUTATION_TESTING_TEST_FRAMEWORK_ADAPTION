#graph.py
import logging
from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from typing import List

log = logging.getLogger(__name__)
from src.llm_runnable import create_runnable
from src.agents import (
    MutantGenerator,
    MutantReflector,
    TestcaseAnalyzer,
    TestcaseGenerator,
    EquivalentChecker,
    HallucinationChecker,
    SourceAnalyzerAgent,  
)
from src.prompts import (
    mutation_agent_prompt,
    reflector_agent_prompt,
    test_case_analyzer_agent_prompt,
    test_case_generator_agent_prompt,
    equivalent_checker_agent_prompt,
    hallucination_agent_prompt,
    source_analyzer_prompt,
)
from src.data_classes import (
    MutationAgentOutput,
    Feedback,
    MutantGenAgentState,
    Mutant,
    GenTestCases,
    TestGenAgentState,
    IsEquivalent,
    EquivalentCheckAgentState,
    Hints,
    HallucinationResult,
    SourceAnalyzerOutputModel,
)
import os
import json


def route_reflector_agent(state, config: RunnableConfig): 
    recursion_limit = config.get("configurable", {}).get("recursion_limit", 5)
    print(f"[DEBUG] Recursion progress: {state.super_step_count} / {recursion_limit}")
    return "reflector_agent" if state.super_step_count < recursion_limit else END


def create_mutant_gen_graph():
    source_analyzer_runnable = create_runnable(source_analyzer_prompt).get_runnable_with_structured_output(
        SourceAnalyzerOutputModel
    )

    test_case_analyzer_agent_runnable = create_runnable(
        test_case_analyzer_agent_prompt
    ).get_runnable_with_structured_output(Hints)

    mutation_chain = create_runnable(mutation_agent_prompt)
    mutation_agent_runnable = mutation_chain.get_runnable_with_structured_output(MutationAgentOutput)

    reflector_runnable = create_runnable(reflector_agent_prompt).get_runnable_with_structured_output(Feedback)

    workflow = StateGraph(MutantGenAgentState)

    workflow.add_node(
        "source_analyzer_agent",
        lambda state, config: SourceAnalyzerAgent(source_analyzer_runnable)(state, config)
    )

    workflow.add_node("testcase_analyzer_agent", TestcaseAnalyzer(test_case_analyzer_agent_runnable))
    workflow.add_node("mutation_agent", MutantGenerator(mutation_agent_runnable, mutation_chain.prompt))
    workflow.add_node("reflector_agent", MutantReflector(reflector_runnable))

    workflow.add_edge(START, "source_analyzer_agent")
    workflow.add_edge("source_analyzer_agent", "testcase_analyzer_agent")
    workflow.add_edge("testcase_analyzer_agent", "mutation_agent")

    workflow.add_conditional_edges("mutation_agent", route_reflector_agent, {
        "reflector_agent": "reflector_agent",
        END: END,
    })
    workflow.add_edge("reflector_agent", "mutation_agent")

    return workflow.compile()


def run_mutant_gen_graph(
        graph,
        config: dict,
        code: str,
        survived_mutants: list,
        killed_mutants: list,
        test_case_data: list,
        dependency_data: dict,
        is_feedback_run: bool = False,
        run_idx: int = 1,
        func_idx: int = 1):

    if config is None or not isinstance(config, dict):
        config = {}

    if test_case_data:
        if isinstance(test_case_data[0], list):
            test_case_data = [str(tc) for sublist in test_case_data for tc in sublist]
        elif not isinstance(test_case_data[0], str):
            test_case_data = [str(tc) for tc in test_case_data]

    ratings_data = None
    ratings_summary = ""

    if not is_feedback_run:
        ratings_data = config.get("configurable", {}).get("ratings")
        if ratings_data is None:
            interm = os.path.join("intermediate", "ratings.json")
            if os.path.exists(interm):
                try:
                    with open(interm, "r", encoding="utf-8") as f:
                        ratings_data = json.load(f)
                except Exception as e:
                    print("[WARNING] Failed loading intermediate/ratings.json:", e)
    else:
        func_dir = os.path.join("ranked", f"run{run_idx}", f"c{func_idx}")
        local_ratings = os.path.join(func_dir, "ratings.json")
        if os.path.exists(local_ratings):
            try:
                with open(local_ratings, "r", encoding="utf-8") as f:
                    ratings_data = json.load(f)
                print(f"[INFO] Using ratings from: {local_ratings}")
            except Exception as e:
                print(f"[WARNING] Failed reading {local_ratings}: {e}")
        if ratings_data is None:
            interm = os.path.join("intermediate", "ratings.json")
            if os.path.exists(interm):
                try:
                    with open(interm, "r", encoding="utf-8") as f:
                        ratings_data = json.load(f)
                except Exception as e:
                    print("[WARNING] Failed loading intermediate/ratings.json:", e)

    if ratings_data is not None:
        ratings_summary = json.dumps(ratings_data, indent=2)
        print("[INFO] Ratings loaded successfully")

    initial_context_summary = config.get("context_summary", "") if isinstance(config, dict) else ""

    graph_config = dict(config)
    graph_config["feedback_run"] = is_feedback_run
    graph_config["run_idx"] = run_idx
    graph_config["func_idx"] = func_idx

    events = graph.stream(
        {
            "function_code": code,
            "context_summary": initial_context_summary,
            "test_case_data": test_case_data,
            "survived_mutants": survived_mutants or [],
            "killed_mutants": killed_mutants or [],
            "dependency_data": dependency_data,
            "ratings_summary": ratings_summary
        },
        config=graph_config,
        stream_mode="updates"
    )

    result = None
    for event in events:
        log.debug(event)
        if "mutation_agent" in event:
            try:
                result = event["mutation_agent"]["mutation_result"].mutants
            except Exception:
                result = getattr(event["mutation_agent"], "mutation_result", None)
                if result and hasattr(result, "mutants"):
                    result = result.mutants

    num_mutants = config.get("configurable", {}).get("num_of_mutants") if isinstance(config, dict) else None
    if num_mutants is not None and result:
        result = result[:num_mutants]

    return result or []


def create_equivalent_checker_graph():
    checker_runnable = create_runnable(equivalent_checker_agent_prompt).get_runnable_with_structured_output(IsEquivalent)
    workflow = StateGraph(EquivalentCheckAgentState)
    workflow.add_node("equivalent_checker_agent", EquivalentChecker(checker_runnable))
    workflow.add_edge(START, "equivalent_checker_agent")
    workflow.add_edge("equivalent_checker_agent", END)
    return workflow.compile()


def run_equivalent_check_graph(graph, code, generated_mutants, dependency_data):
    events = graph.stream({
        "function_code": code,
        "generated_mutants": generated_mutants,
        "dependency_data": dependency_data
    }, stream_mode="updates")
    for event in events:
        log.debug(event)
        print("[INFO] Received Non equivalent mutants from equivalent_checker_agent...")
    result = event["equivalent_checker_agent"]
    return result.get("filtered_mutants", []), result.get("survived_mutants", [])


def create_test_gen_graph():
    runnable = create_runnable(test_case_generator_agent_prompt).get_runnable_with_structured_output(GenTestCases)
    workflow = StateGraph(TestGenAgentState)
    workflow.add_node("testcase_generator_agent", TestcaseGenerator(runnable))
    workflow.add_edge(START, "testcase_generator_agent")
    workflow.add_edge("testcase_generator_agent", END)
    return workflow.compile()


def run_test_gen_graph(graph, code, survived_mutants, test_case_data, dependency_data):
    if test_case_data:
        if isinstance(test_case_data[0], list):
            test_case_data = [str(tc) for sublist in test_case_data for tc in sublist]
        elif not isinstance(test_case_data[0], str):
            test_case_data = [str(tc) for tc in test_case_data]

    events = graph.stream({
        "function_code": code,
        "survived_mutants": survived_mutants,
        "test_case_data": test_case_data,
        "dependency_data": dependency_data
    }, stream_mode="updates")
    for event in events:
        log.debug(event)
        print("[INFO] Test cases analysed by testcase_generator_agent...")
    response = event["testcase_generator_agent"]
    return response.gen_test_cases if hasattr(response, "gen_test_cases") else []


def create_hallucination_graph():
    checker_runnable = create_runnable(hallucination_agent_prompt).get_runnable_with_structured_output(HallucinationResult)
    workflow = StateGraph(EquivalentCheckAgentState)
    workflow.add_node("hallucination_checker_agent", HallucinationChecker(checker_runnable, "hallucinations.json"))
    workflow.add_edge(START, "hallucination_checker_agent")
    workflow.add_edge("hallucination_checker_agent", END)
    return workflow.compile()


def run_hallucination_check_graph(graph, code, generated_mutants, dependency_data):
    events = graph.stream({
        "function_code": code,
        "generated_mutants": generated_mutants,
        "dependency_data": dependency_data
    }, stream_mode="updates")
    for event in events:
        log.debug(event)
        print("[INFO] Received hallucination check results from hallucination_checker_agent...")
    result = event["hallucination_checker_agent"]
    return result.get("filtered_mutants", []), result.get("hallucinations", [])

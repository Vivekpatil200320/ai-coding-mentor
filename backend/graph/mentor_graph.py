"""LangGraph multi-agent orchestration for the AI Coding Mentor.

Model note: the original spec called for claude-sonnet-4-6 via
langchain_anthropic.ChatAnthropic. This project runs on a zero-budget
NVIDIA free-tier stack instead (see backend/agents/llm.py) — Claude would
fail immediately without a paid ANTHROPIC_API_KEY, which this project
deliberately doesn't have. All five agents use ChatNVIDIA models per the
tiered assignment agreed on earlier in this build.

Inter-agent communication is state passing only, never tool_calls — each
node reads and returns MentorState fields, per the original spec.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agents.analysis_agent import analysis_node
from agents.evaluation_agent import evaluation_node
from agents.execution_agent import execution_node, route_after_execution
from agents.mentor_agent import mentor_node
from agents.router_agent import router_node
from graph.state import MentorState


def build_mentor_graph():
    graph = StateGraph(MentorState)

    graph.add_node("router", router_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("mentor", mentor_node)
    graph.add_node("execution", execution_node)
    graph.add_node("evaluation", evaluation_node)

    graph.add_edge(START, "router")
    graph.add_edge("router", "analysis")
    graph.add_edge("analysis", "mentor")
    graph.add_edge("mentor", "execution")
    graph.add_conditional_edges(
        "execution",
        route_after_execution,
        {"evaluation": "evaluation", "mentor": "mentor"},
    )
    graph.add_edge("evaluation", END)

    # interrupt_before=["execution"] is what "mentor -> (user submits
    # code) -> execution" means in practice: a real invocation pauses
    # after the mentor's turn and waits for the API layer to resume it
    # once the user actually submits code, using session_id as the
    # checkpointer's thread_id — this is not an automatic LLM-to-LLM
    # transition.
    return graph.compile(checkpointer=MemorySaver(), interrupt_before=["execution"])

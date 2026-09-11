"""
Wires the four agents into one LangGraph pipeline: data collector, then risk
assessor, then compliance checker, then decision maker, in that fixed order
(the phase's own doc calls this "linear — no cycles needed").

The one branch in the graph is right after data collection: if the
application could not be fetched, the graph ends there rather than asking
the other three agents to reason about data that does not exist.
"""

import structlog
from langgraph.graph import END, StateGraph

from llm_provider import enable_langsmith
from multi_agent.agents.compliance_checker import compliance_checker
from multi_agent.agents.data_collector import data_collector
from multi_agent.agents.decision_maker import decision_maker
from multi_agent.agents.risk_assessor import risk_assessor
from multi_agent.state import LoanProcessingState, initial_state
from app.utils.logging_config import configure_logging
from app.utils.otel_config import get_tracer, setup_telemetry

logger = structlog.get_logger()

LANGSMITH_PROJECT = "AI-Readiness-POC-01-P5"


def should_continue_after_data_collection(state: LoanProcessingState) -> str:
    """The graph's one conditional edge: stop here if data collection failed."""
    log = logger.bind(poc_id="POC-01", phase=5)
    if state.get("errors"):
        log.warning("supervisor_routing", operation="reasoning",
                    from_agent="data_collector", to_agent="END",
                    reason=f"errors: {state['errors']}")
        return "end"
    log.info("supervisor_routing", operation="reasoning",
              from_agent="data_collector", to_agent="risk_assessor")
    return "continue"


def build_loan_evaluation_graph():
    """Build and compile the four-agent loan evaluation graph."""
    workflow = StateGraph(LoanProcessingState)

    workflow.add_node("data_collector", data_collector)
    workflow.add_node("risk_assessor", risk_assessor)
    workflow.add_node("compliance_checker", compliance_checker)
    workflow.add_node("decision_maker", decision_maker)

    workflow.set_entry_point("data_collector")

    workflow.add_conditional_edges(
        "data_collector",
        should_continue_after_data_collection,
        {"continue": "risk_assessor", "end": END},
    )

    workflow.add_edge("risk_assessor", "compliance_checker")
    workflow.add_edge("compliance_checker", "decision_maker")
    workflow.add_edge("decision_maker", END)

    return workflow.compile()


def evaluate_loan_application(application_id: str) -> LoanProcessingState:
    """Run the full four-agent evaluation for one loan application."""
    configure_logging()
    setup_telemetry()
    # Known wart, left deliberately. This sets a process-global
    # LANGCHAIN_PROJECT, and now that reviews also run from the chat endpoint, a
    # Phase 3 question answered at the same moment can have its trace filed
    # under the P5 project. Fixing it properly means a lock or threading the
    # project name through every LangChain call — a lot of machinery for a
    # diagnostic nobody's decisions depend on. Traces are for us, not for the
    # bank, so a misfiled one costs nothing real.
    enable_langsmith(LANGSMITH_PROJECT)

    log = logger.bind(poc_id="POC-01", phase=5, application_id=application_id)
    tracer = get_tracer()

    with tracer.start_as_current_span("graph.execute") as span:
        span.set_attribute("graph.application_id", application_id)
        span.set_attribute("graph.input_node", "START")

        graph = build_loan_evaluation_graph()

        log.info("graph_execution_started", operation="reasoning")

        final_state = graph.invoke(
            initial_state(application_id),
            config={"metadata": {"poc_id": "POC-01", "phase": 5, "application_id": application_id}},
        )

        span.set_attribute("graph.final_decision", final_state.get("final_decision", "unknown"))
        span.set_attribute("graph.agents_executed", len(final_state.get("messages", [])))

        log.info("graph_execution_complete", operation="reasoning",
                  final_decision=final_state.get("final_decision"),
                  agents_executed=len(final_state.get("messages", [])),
                  errors=final_state.get("errors", []))

        return final_state

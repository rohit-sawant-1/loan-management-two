"""
The ReAct agent: one loop that reads a question, decides which of the five
tools to call (if any), reads the result, and repeats until it can answer.

ReAct means the model alternates between writing a **Thought** (its reasoning),
an **Action** (which tool to call and with what input), and reading the
**Observation** (the tool's answer) — until it decides it knows enough to give
a **Final Answer**. This is what lets one loop answer "what is the status of
application 5, and what documents does a home loan need?" by calling two
different tools and combining what they say.

The prompt is built by hand rather than pulled from LangChain's hub
(`hub.pull("hwchase17/react")`), for two reasons: `langchain.hub` no longer
exists at this LangChain version, and pulling a prompt from the internet at
startup is one more thing that can fail during a demo. This is the same
prompt shape, held locally.
"""

from __future__ import annotations

import structlog
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate

from agent.prompts import LOAN_AGENT_SYSTEM_PROMPT
from agent.tools import ALL_TOOLS
from agent.write_tools import WRITE_TOOLS
from app.domain import rules
from app.utils.logging_config import configure_logging
from app.utils.otel_config import get_tracer, setup_telemetry
from llm_provider import enable_langsmith, get_llm

logger = structlog.get_logger()

LANGSMITH_PROJECT = "AI-Readiness-POC-01-P3"

MAX_ITERATIONS = 8

# The classic ReAct format. `{tools}` and `{tool_names}` are filled in by
# create_react_agent from the tool list; `{input}` and `{agent_scratchpad}` are
# filled in on every call.
REACT_TEMPLATE = LOAN_AGENT_SYSTEM_PROMPT + """

You have access to the following tools:

{tools}

Use the following format exactly:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

# Staff get the same prompt plus the rules for changing records. The extra
# paragraph exists because a write tool returns "CONFIRMATION NEEDED" rather
# than a result, and without being told what that means the model tends to
# treat it as a failure and try again — which would propose the same change
# twice.
STAFF_EXTRA = """

You are talking to bank staff, so you also have tools that change records.

Three rules about those, which you must follow exactly:

- When a change tool answers with CONFIRMATION NEEDED, the change has NOT
  happened yet. Give the person that exact description and ask them to reply
  YES. Then stop and give your Final Answer. Do not call the tool again, and do
  not call a different tool to check whether it worked — it has not.
- Never guess an application number, an amount, or a status. If the person has
  not said which application they mean, ask them.
- A status change always needs a reason. If they have not given one, ask for it
  before proposing the change."""

STAFF_REACT_TEMPLATE = LOAN_AGENT_SYSTEM_PROMPT + STAFF_EXTRA + """

You have access to the following tools:

{tools}

Use the following format exactly:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, must be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat)
Thought: I now know the final answer
Final Answer: the final answer to the original question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""


def tools_for(role: str | None) -> list:
    """
    Which tools this person's assistant is allowed to have.

    Staff get the three write tools on top of the five read-only ones; a
    customer gets exactly what they got before. The difference matters more
    than it looks: a tool that is not in the list cannot be called at all, so
    a customer's agent has no way to even propose changing a record.

    Officers and managers get the **same** list. The one thing that separates
    them is disbursement, and the API already refuses that to anyone who is not
    a manager (`application_service.py:271`). Repeating that rule here would be
    a second place to keep in step, and two copies of a permission rule are how
    they drift apart.
    """
    if role in rules.STAFF_ROLES:
        return [*ALL_TOOLS, *WRITE_TOOLS]
    return list(ALL_TOOLS)


def build_agent(role: str | None = None) -> AgentExecutor:
    """
    Build the agent executor for someone in this role.

    `max_iterations=8` caps how many Thought/Action rounds the agent may take,
    so a confused loop cannot run forever. `handle_parsing_errors=True` means a
    single malformed step is reported back to the model to correct rather than
    crashing the whole conversation. `return_intermediate_steps=True` is what
    lets `run_agent` (and the trainer's tests) see which tools actually ran.

    `role` defaults to None, which builds the read-only agent — the shape the
    trainer's Phase 3 tests call with no arguments.
    """
    configure_logging()
    setup_telemetry()
    enable_langsmith(LANGSMITH_PROJECT)

    tools = tools_for(role)
    template = REACT_TEMPLATE if role not in rules.STAFF_ROLES else STAFF_REACT_TEMPLATE

    llm = get_llm(temperature=0)   # fully predictable: the same question picks the same tool
    prompt = PromptTemplate.from_template(template)
    agent = create_react_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        max_iterations=MAX_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )


def run_agent(question: str, executor: AgentExecutor | None = None) -> dict:
    """
    Ask the agent one question. Returns the executor's own result dict —
    `output` (the final answer) and `intermediate_steps` (which tools ran, in
    order, with what they returned) — which is exactly the shape the trainer's
    end-to-end tests expect.
    """
    if executor is None:
        executor = build_agent()

    tracer = get_tracer()
    with tracer.start_as_current_span("agent.reasoning") as span:
        span.set_attribute("agent.question", question[:200])
        result = executor.invoke({"input": question})
        steps = result.get("intermediate_steps", [])
        span.set_attribute("agent.steps", len(steps))
        span.set_attribute("agent.tools_used", ",".join(s[0].tool for s in steps))
        logger.info("agent_reasoning_completed", operation="reasoning",
                    question=question[:200], steps=len(steps),
                    tools_used=[s[0].tool for s in steps])
        return result

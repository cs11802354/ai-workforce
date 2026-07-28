"""The two capability catalogues.

SKILLS are prose: they get folded into the system prompt and shape how the model
reasons about a request. They are not callable.

TOOLS are JSON-schema definitions handed to the model in `tools=[...]`. The model
emits a tool_use block, the workflow dispatches it, and a result comes back. The
finance tools below are deliberately `enabled: False` — the dispatch path is real,
only the adapter bodies are stubs, so connecting a real terminal later is a
one-function change in the worker.
"""

SKILLS = [
    {
        "id": "web_search",
        "name": "Web Search",
        "description": "Look things up on the public web.",
        "prompt": "You can search the web for current information.",
    },
    {
        "id": "calculator",
        "name": "Calculator",
        "description": "Do arithmetic and unit conversions.",
        "prompt": "You are careful and precise with arithmetic and unit conversions.",
    },
    {
        "id": "code_interpreter",
        "name": "Code Interpreter",
        "description": "Reason about and run small snippets of code.",
        "prompt": "You can read, write, and reason about code.",
    },
    {
        "id": "email_sender",
        "name": "Email Sender",
        "description": "Draft and send email on the user's behalf.",
        "prompt": "You can draft email. Always show a draft before sending.",
    },
    {
        "id": "calendar",
        "name": "Calendar",
        "description": "Read and create calendar events.",
        "prompt": "You can read and propose calendar events.",
    },
]

# Finance desks an analyst actually sits in front of. All disabled for now.
TOOLS = [
    {
        "id": "bloomberg",
        "name": "Bloomberg Terminal",
        "description": "Real-time market data, pricing, and news.",
        "enabled": False,
    },
    {
        "id": "lseg_workspace",
        "name": "LSEG Workspace",
        "description": "Refinitiv market data, filings, and estimates.",
        "enabled": False,
    },
    {
        "id": "factset",
        "name": "FactSet",
        "description": "Company fundamentals, ownership, and screening.",
        "enabled": False,
    },
    {
        "id": "capital_iq",
        "name": "S&P Capital IQ",
        "description": "Comps, transactions, and credit data.",
        "enabled": False,
    },
    {
        "id": "pitchbook",
        "name": "PitchBook",
        "description": "Private markets, VC and PE deal data.",
        "enabled": False,
    },
    {
        "id": "morningstar",
        "name": "Morningstar Direct",
        "description": "Fund research, ratings, and performance.",
        "enabled": False,
    },
    {
        "id": "aladdin",
        "name": "BlackRock Aladdin",
        "description": "Portfolio construction and risk analytics.",
        "enabled": False,
    },
    {
        "id": "sec_edgar",
        "name": "SEC EDGAR",
        "description": "Company filings — 10-K, 10-Q, 8-K, S-1.",
        "enabled": False,
    },
]

SKILLS_BY_ID = {s["id"]: s for s in SKILLS}
TOOLS_BY_ID = {t["id"]: t for t in TOOLS}

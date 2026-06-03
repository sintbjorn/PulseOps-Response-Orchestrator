from prometheus_client import Counter, Histogram

execution_counter = Counter(
    "pulseops_executions_total",
    "Runbook executions by status.",
    ["status", "severity", "target"],
)

step_counter = Counter(
    "pulseops_execution_steps_total",
    "Runbook step outcomes.",
    ["step_type", "status"],
)

policy_simulation_counter = Counter(
    "pulseops_policy_simulations_total",
    "Policy simulation requests.",
    ["matched"],
)

execution_duration_seconds = Histogram(
    "pulseops_execution_duration_seconds",
    "End-to-end runbook execution duration.",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

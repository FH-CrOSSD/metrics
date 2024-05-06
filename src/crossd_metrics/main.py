#!/usr/bin/env python3
# -*- coding=utf-8 -*-

from crossd_metrics.metrics import get_metrics
from crossd_metrics.Repository import Repository
from rich.console import Console

console = Console(force_terminal=True)
console.rule("Data Retrieval")

res = (
    Repository(owner="inconshreveable", name="ngrok")
    .ask_all()
    .execute(rate_limit=True, verbose=True)
)

console.log(res)

console.rule("Metrics")
print(get_metrics(res))

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_error_handlers
from app.core.errors import DomainError, ErrorCode
from app.ingestion.runtime.errors import retryable_error

BACKEND = Path(__file__).resolve().parents[2]
CONTRACTS = json.loads(
    Path(__file__).with_name("service_error_contracts.json").read_text()
)


def _raise_sites() -> dict[str, ast.Call]:
    sites = {}
    for area in ("chat", "ingestion"):
        for path in sorted((BACKEND / "app" / area).rglob("*.py")):
            calls = sorted(
                (
                    node
                    for node in ast.walk(ast.parse(path.read_text()))
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id in {"DomainError", "HTTPException"}
                ),
                key=lambda node: node.lineno,
            )
            for ordinal, call in enumerate(calls):
                assert isinstance(call.func, ast.Name)
                assert call.func.id == "DomainError"
                sites[f"{path.relative_to(BACKEND)}:{ordinal}"] = call
    return sites


SITES = _raise_sites()


def test_every_service_raise_site_has_a_response_contract() -> None:
    assert set(SITES) == {contract["site"] for contract in CONTRACTS}


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda item: item["site"])
def test_service_raise_site_preserves_response(contract: dict[str, Any]) -> None:
    call = SITES[contract["site"]]
    assert ast.unparse(call.args[1]) == contract["detail_expression"]
    exception = eval(
        compile(ast.Expression(call), "<service-error>", "eval"),
        {
            "DomainError": DomainError,
            "ErrorCode": ErrorCode,
            "stage": SimpleNamespace(value="parsing_structure"),
            "member": SimpleNamespace(id="release-id"),
            "gates": ["gate-b", "gate-a", "gate-b"],
            "quality_gates": ["gate-a"],
            "exc": ValueError("provider failure"),
            "instrument_type": "statute",
        },
    )
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/failure")
    def failure() -> None:
        raise exception

    with TestClient(app) as client:
        response = client.get("/failure")
    assert response.status_code == contract["status"]
    assert response.json()["detail"] == contract["detail"]
    assert response.json()["code"] == exception.code
    assert retryable_error(exception) == (contract["status"] >= 500)

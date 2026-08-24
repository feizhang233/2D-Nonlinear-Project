"""P10 service-level limits, cancellation, and server-failure transactions."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from threading import Event

import pytest

from nonlinear_api import (
    AnalysisRequest,
    AnalysisService,
    AnalysisStatus,
    ApiErrorCategory,
    ApiLimits,
)
from nonlinear_api.service import ApiProblem
from nonlinear_core import get_adapter, solve_load_control

ROOT = Path(__file__).resolve().parents[2]
ARCH = ROOT / "tests" / "fixtures" / "p9" / "shallow-arch-snap-through.json"


def _document() -> dict[str, object]:
    return json.loads(ARCH.read_text(encoding="utf-8"))


def test_structurally_valid_model_can_be_ineligible_for_synchronous_dof_limit():
    service = AnalysisService(limits=ApiLimits(max_dofs=8))

    validation = service.validate_model(_document())

    assert validation.valid
    assert not validation.execution_eligible
    assert validation.dof_count == 9
    assert validation.limit_error is not None
    assert validation.limit_error.code == "DOF_LIMIT_EXCEEDED"
    with pytest.raises(ApiProblem) as caught:
        asyncio.run(service.submit(AnalysisRequest(model=_document())))
    assert caught.value.status_code == 413


def test_task_cancellation_discards_result_and_retains_cancelled_record():
    started = Event()
    release = Event()

    def blocking_runner(model, payload):
        started.set()
        assert release.wait(timeout=2.0)
        return solve_load_control(
            get_adapter(model),
            model,
            target_load_factor=payload.target_load_factor or 0.1,
        ).result

    service = AnalysisService(runner=blocking_runner)

    async def scenario() -> None:
        task = asyncio.create_task(
            service.submit(AnalysisRequest(model=_document(), target_load_factor=0.1))
        )
        assert await asyncio.wait_for(asyncio.to_thread(started.wait), timeout=1.0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        records = service.store.snapshot()
        assert len(records) == 1
        assert records[0].status is AnalysisStatus.CANCELLED
        assert records[0].result is None
        assert records[0].error is not None
        assert records[0].error.code == "CLIENT_CANCELLED"
        release.set()

    asyncio.run(scenario())


def test_unexpected_runner_error_becomes_server_record_without_fake_result():
    def broken_runner(model, payload):
        raise RuntimeError(f"intentional {model.model_id}/{payload.execution_mode}")

    service = AnalysisService(runner=broken_runner)

    with pytest.raises(ApiProblem) as caught:
        asyncio.run(service.submit(AnalysisRequest(model=_document())))

    assert caught.value.status_code == 500
    assert caught.value.error.category is ApiErrorCategory.SERVER
    record = service.store.snapshot()[0]
    assert record.status is AnalysisStatus.FAILED
    assert record.result is None
    assert record.error is not None
    assert record.error.code == "ANALYSIS_EXECUTION_ERROR"

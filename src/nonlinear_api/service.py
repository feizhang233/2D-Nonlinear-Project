"""P10 validation, local execution, live progress, restart, and cancellation safety."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event, RLock, Thread
from typing import NoReturn
from uuid import UUID, uuid4

from nonlinear_api.schemas import (
    AnalysisProgress,
    AnalysisRecord,
    AnalysisRequest,
    AnalysisStatus,
    ApiErrorCategory,
    ApiErrorDetail,
    ApiLimits,
    ExecutionMode,
    ModelValidationResponse,
)
from nonlinear_core import (
    ArcLengthIncrement,
    ControlMethod,
    ModelInput,
    PostResult,
    ResultField,
    ResultLocation,
    SolveProgress,
    SolverCancelled,
    SolveResult,
    SolveStatus,
    StateTransitionError,
    StepStatus,
    deserialize_restart,
    get_adapter,
    model_sha256,
    serialize_restart,
    solve_adaptive_displacement_control,
    solve_adaptive_load_control,
    solve_arc_length,
    validate_model_input,
)

AnalysisRunner = Callable[[ModelInput, AnalysisRequest], SolveResult]


class ApiProblem(Exception):
    """One already-classified HTTP problem safe to serialize to the client."""

    def __init__(self, status_code: int, error: ApiErrorDetail) -> None:
        super().__init__(error.message)
        self.status_code = status_code
        self.error = error


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _replace_record(record: AnalysisRecord, **changes: object) -> AnalysisRecord:
    document = record.model_dump(mode="python")
    document.update(changes)
    return AnalysisRecord.model_validate(document)


class AnalysisStore:
    """Thread-safe in-process P10 store; replaceable by a durable queue in a later phase."""

    def __init__(self) -> None:
        self._records: dict[UUID, AnalysisRecord] = {}
        self._lock = RLock()

    def put(self, record: AnalysisRecord) -> AnalysisRecord:
        with self._lock:
            self._records[record.analysis_id] = record
        return record

    def get(self, analysis_id: UUID) -> AnalysisRecord:
        with self._lock:
            try:
                return self._records[analysis_id]
            except KeyError as error:
                raise KeyError(str(analysis_id)) from error

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def snapshot(self) -> tuple[AnalysisRecord, ...]:
        with self._lock:
            return tuple(self._records.values())


class AnalysisService:
    """Validate and run bounded small models without weakening core failure evidence."""

    def __init__(
        self,
        *,
        limits: ApiLimits | None = None,
        store: AnalysisStore | None = None,
        runner: AnalysisRunner | None = None,
    ) -> None:
        self.limits = limits or ApiLimits()
        self.store = store or AnalysisStore()
        self._runner = runner or _run_analysis
        self._uses_default_runner = runner is None
        self._cancellation_events: dict[UUID, Event] = {}
        self._record_lock = RLock()

    def validate_model(self, document: object) -> ModelValidationResponse:
        validation = validate_model_input(document)
        if not validation.valid or validation.model is None:
            return ModelValidationResponse(
                valid=False,
                execution_eligible=False,
                errors=validation.errors,
            )
        model = validation.model
        dof_count = len(model.ordered_dof_refs())
        if dof_count > self.limits.max_dofs:
            error = ApiErrorDetail(
                category=ApiErrorCategory.INPUT,
                code="DOF_LIMIT_EXCEEDED",
                message=(
                    f"model has {dof_count} DOFs; synchronous API limit is "
                    f"{self.limits.max_dofs}"
                ),
                location="$.nodes",
                details={"dof_count": dof_count, "max_dofs": self.limits.max_dofs},
            )
            return ModelValidationResponse(
                valid=True,
                execution_eligible=False,
                model=model,
                dof_count=dof_count,
                limit_error=error,
            )
        return ModelValidationResponse(
            valid=True,
            execution_eligible=True,
            model=model,
            dof_count=dof_count,
        )

    async def submit(self, payload: AnalysisRequest) -> AnalysisRecord:
        prepared = self.validate_model(payload.model)
        if not prepared.valid or prepared.model is None:
            first = prepared.errors[0] if prepared.errors else None
            details = {
                "errors": [item.model_dump(mode="json") for item in prepared.errors]
            }
            raise ApiProblem(
                422,
                ApiErrorDetail(
                    category=ApiErrorCategory.INPUT,
                    code="MODEL_VALIDATION_FAILED",
                    message="analysis model failed contract validation",
                    location=None if first is None else first.json_path,
                    details=details,
                ),
            )
        if not prepared.execution_eligible:
            assert prepared.limit_error is not None
            raise ApiProblem(413, prepared.limit_error)

        model = prepared.model
        self._validate_control_request(model, payload)
        adapter = get_adapter(model)
        adapter_validation = adapter.validate(model)
        if not adapter_validation.valid:
            first = adapter_validation.errors[0]
            raise ApiProblem(
                422,
                ApiErrorDetail(
                    category=ApiErrorCategory.INPUT,
                    code="ADAPTER_MODEL_INVALID",
                    message="selected model adapter rejected the analysis input",
                    location=None,
                    details={
                        "adapter_id": adapter.adapter_id,
                        "errors": [
                            {
                                "code": item.code,
                                "message": item.message,
                                "entity_id": item.entity_id,
                            }
                            for item in adapter_validation.errors
                        ],
                        "first_error": first.message,
                    },
                ),
            )
        self._validate_restart(model, payload, adapter.adapter_id)

        assert prepared.dof_count is not None
        created = _utcnow()
        record = AnalysisRecord(
            analysis_id=uuid4(),
            status=AnalysisStatus.QUEUED,
            execution_mode=payload.execution_mode,
            created_at=created,
            model_id=model.model_id,
            model_sha256=model_sha256(model),
            control_method=model.analysis.control_method.value,
            dof_count=prepared.dof_count,
            progress=AnalysisProgress(message="analysis is queued"),
        )
        self.store.put(record)
        self._cancellation_events[record.analysis_id] = Event()

        if payload.execution_mode is ExecutionMode.ASYNCHRONOUS:
            Thread(
                target=self._run_background,
                args=(record.analysis_id, model, payload),
                name=f"nonlinear-analysis-{record.analysis_id}",
                daemon=True,
            ).start()
            return record

        record = self._mark_running(record.analysis_id)
        try:
            result = await asyncio.to_thread(
                self._execute,
                record.analysis_id,
                model,
                payload,
            )
        except asyncio.CancelledError:
            self.mark_cancelled(record.analysis_id)
            raise
        except SolverCancelled:
            return self.mark_cancelled(record.analysis_id)
        except Exception as error:  # noqa: BLE001 - converted to a stable server contract
            failed = self._finish_unexpected(record.analysis_id, error)
            assert failed.error is not None
            detail = failed.error
            raise ApiProblem(500, detail) from error
        return self._finish_result(record.analysis_id, result)

    def _mark_running(self, analysis_id: UUID) -> AnalysisRecord:
        with self._record_lock:
            record = self.store.get(analysis_id)
            if record.status is not AnalysisStatus.QUEUED:
                return record
            return self.store.put(
                _replace_record(
                    record,
                    status=AnalysisStatus.RUNNING,
                    started_at=_utcnow(),
                    progress=AnalysisProgress(message="analysis is running"),
                )
            )

    def _execute(
        self,
        analysis_id: UUID,
        model: ModelInput,
        payload: AnalysisRequest,
    ) -> SolveResult:
        def report(progress: SolveProgress) -> None:
            self._report_progress(analysis_id, progress)

        if self._uses_default_runner:
            return _run_analysis(model, payload, progress_callback=report)
        report(SolveProgress(0, 0, 0, "custom analysis runner is running"))
        return self._runner(model, payload)

    def _run_background(
        self,
        analysis_id: UUID,
        model: ModelInput,
        payload: AnalysisRequest,
    ) -> None:
        record = self._mark_running(analysis_id)
        if record.status is AnalysisStatus.CANCELLED:
            return
        try:
            result = self._execute(analysis_id, model, payload)
        except SolverCancelled:
            self.mark_cancelled(analysis_id)
        except Exception as error:  # noqa: BLE001 - persisted as a stable server record
            self._finish_unexpected(analysis_id, error)
        else:
            self._finish_result(analysis_id, result)

    def _report_progress(self, analysis_id: UUID, progress: SolveProgress) -> None:
        event = self._cancellation_events[analysis_id]
        if event.is_set():
            raise SolverCancelled
        with self._record_lock:
            record = self.store.get(analysis_id)
            if record.status is AnalysisStatus.CANCELLED:
                raise SolverCancelled
            if record.status is not AnalysisStatus.RUNNING:
                return
            self.store.put(
                _replace_record(
                    record,
                    progress=AnalysisProgress(
                        current_step=progress.step_index,
                        current_iteration=progress.iteration_index,
                        accepted_steps=progress.accepted_steps,
                        message=progress.message,
                    ),
                )
            )

    def _finish_result(self, analysis_id: UUID, result: SolveResult) -> AnalysisRecord:
        with self._record_lock:
            record = self.store.get(analysis_id)
            if record.status is AnalysisStatus.CANCELLED:
                return record
            accepted_steps = sum(step.status is StepStatus.ACCEPTED for step in result.steps)
            if result.status is SolveStatus.SUCCEEDED:
                finished = _replace_record(
                    record,
                    status=AnalysisStatus.SUCCEEDED,
                    completed_at=_utcnow(),
                    progress=AnalysisProgress(
                        current_step=record.progress.current_step,
                        current_iteration=record.progress.current_iteration,
                        accepted_steps=accepted_steps,
                        message="analysis completed",
                    ),
                    result=result,
                )
            else:
                failure = result.failures[-1]
                detail = ApiErrorDetail(
                    category=ApiErrorCategory.COMPUTATION,
                    code=failure.code.value,
                    message=failure.message,
                    location=failure.json_path,
                    details={
                        "step_index": failure.step_index,
                        "iteration_index": failure.iteration_index,
                        "solver_details": failure.details,
                    },
                )
                finished = _replace_record(
                    record,
                    status=AnalysisStatus.FAILED,
                    completed_at=_utcnow(),
                    progress=AnalysisProgress(
                        current_step=record.progress.current_step,
                        current_iteration=record.progress.current_iteration,
                        accepted_steps=accepted_steps,
                        message="analysis completed with a numerical failure",
                    ),
                    result=result,
                    error=detail,
                )
            return self.store.put(finished)

    def _finish_unexpected(self, analysis_id: UUID, error: Exception) -> AnalysisRecord:
        with self._record_lock:
            record = self.store.get(analysis_id)
            if record.status is AnalysisStatus.CANCELLED:
                return record
            detail = ApiErrorDetail(
                category=ApiErrorCategory.SERVER,
                code="ANALYSIS_EXECUTION_ERROR",
                message="analysis execution failed unexpectedly",
                details={"exception_type": type(error).__name__},
            )
            return self.store.put(
                _replace_record(
                    record,
                    status=AnalysisStatus.FAILED,
                    completed_at=_utcnow(),
                    progress=AnalysisProgress(message="server-side execution failed"),
                    error=detail,
                )
            )

    def get(self, analysis_id: UUID) -> AnalysisRecord:
        try:
            return self.store.get(analysis_id)
        except KeyError:
            raise ApiProblem(
                404,
                ApiErrorDetail(
                    category=ApiErrorCategory.INPUT,
                    code="ANALYSIS_NOT_FOUND",
                    message=f"analysis {analysis_id} was not found",
                    location="$.analysis_id",
                ),
            ) from None

    def mark_cancelled(self, analysis_id: UUID) -> AnalysisRecord:
        with self._record_lock:
            try:
                record = self.store.get(analysis_id)
            except KeyError:
                return self.get(analysis_id)
            if record.status in {
                AnalysisStatus.SUCCEEDED,
                AnalysisStatus.FAILED,
                AnalysisStatus.CANCELLED,
            }:
                return record
            self._cancellation_events.setdefault(analysis_id, Event()).set()
            started_at = record.started_at or _utcnow()
            cancelled = _replace_record(
                record,
                status=AnalysisStatus.CANCELLED,
                started_at=started_at,
                completed_at=_utcnow(),
                progress=AnalysisProgress(
                    current_step=record.progress.current_step,
                    current_iteration=record.progress.current_iteration,
                    accepted_steps=record.progress.accepted_steps,
                    message="client cancelled the analysis; computed output was discarded",
                ),
                result=None,
                error=ApiErrorDetail(
                    category=ApiErrorCategory.COMPUTATION,
                    code="CLIENT_CANCELLED",
                    message="analysis request was cancelled by the client",
                ),
            )
            return self.store.put(cancelled)

    def _validate_restart(
        self,
        model: ModelInput,
        payload: AnalysisRequest,
        adapter_id: str,
    ) -> None:
        if payload.restart is None:
            return
        try:
            state = deserialize_restart(
                json.dumps(payload.restart.committed_state),
                model=model,
                expected_adapter_id=adapter_id,
            )
            increment = (
                None
                if payload.restart.arc_length_increment is None
                else ArcLengthIncrement.from_payload(payload.restart.arc_length_increment)
            )
        except (StateTransitionError, TypeError, ValueError) as error:
            self._input_problem(
                "RESTART_INVALID",
                f"analysis restart is invalid: {error}",
                "$.restart",
            )
        if model.analysis.control_method is ControlMethod.ARC_LENGTH:
            if state.step_index > 0 and increment is None:
                self._input_problem(
                    "ARC_INCREMENT_REQUIRED",
                    "an arc-length continuation requires the previous converged increment",
                    "$.restart.arc_length_increment",
                )
        elif increment is not None:
            self._input_problem(
                "ARC_INCREMENT_NOT_ALLOWED",
                "arc_length_increment is accepted only for arc-length control",
                "$.restart.arc_length_increment",
            )

    def _validate_control_request(self, model: ModelInput, payload: AnalysisRequest) -> None:
        control = model.analysis.control_method
        if control is ControlMethod.LOAD:
            if payload.number_of_steps is not None:
                self._input_problem(
                    "CONTROL_PARAMETER_INVALID",
                    "number_of_steps is not accepted for load control; use target_load_factor",
                    "$.number_of_steps",
                )
        else:
            if payload.target_load_factor is not None:
                self._input_problem(
                    "CONTROL_PARAMETER_INVALID",
                    "target_load_factor is only accepted for load control",
                    "$.target_load_factor",
                )
            steps = payload.number_of_steps or 1
            if steps > model.analysis.step_control.max_steps:
                self._input_problem(
                    "STEP_LIMIT_EXCEEDED",
                    "number_of_steps exceeds model.analysis.step_control.max_steps",
                    "$.number_of_steps",
                    details={
                        "number_of_steps": steps,
                        "max_steps": model.analysis.step_control.max_steps,
                    },
                )

    def _input_problem(
        self,
        code: str,
        message: str,
        location: str,
        *,
        details: dict[str, object] | None = None,
    ) -> NoReturn:
        raise ApiProblem(
            422,
            ApiErrorDetail(
                category=ApiErrorCategory.INPUT,
                code=code,
                message=message,
                location=location,
                details=details or {},
            ),
        )


def _run_analysis(
    model: ModelInput,
    payload: AnalysisRequest,
    *,
    progress_callback: Callable[[SolveProgress], None] | None = None,
) -> SolveResult:
    adapter = get_adapter(model)
    control = model.analysis.control_method
    initial_state = None
    previous_increment = None
    if payload.restart is not None:
        initial_state = deserialize_restart(
            json.dumps(payload.restart.committed_state),
            model=model,
            expected_adapter_id=adapter.adapter_id,
        )
        if payload.restart.arc_length_increment is not None:
            previous_increment = ArcLengthIncrement.from_payload(
                payload.restart.arc_length_increment
            )
    if control is ControlMethod.LOAD:
        solution = solve_adaptive_load_control(
            adapter,
            model,
            target_load_factor=(
                1.0 if payload.target_load_factor is None else payload.target_load_factor
            ),
            initial_state=initial_state,
            progress_callback=progress_callback,
        )
    elif control is ControlMethod.DISPLACEMENT:
        solution = solve_adaptive_displacement_control(
            adapter,
            model,
            number_of_steps=payload.number_of_steps or 1,
            initial_state=initial_state,
            progress_callback=progress_callback,
        )
    else:
        solution = solve_arc_length(
            adapter,
            model,
            number_of_steps=payload.number_of_steps or 1,
            initial_state=initial_state,
            previous_increment=previous_increment,
            progress_callback=progress_callback,
        )
    result = solution.result
    committed = solution.committed_state
    if committed is not None:
        restart: dict[str, object] = {
            "restart_schema_version": "1.0.0",
            "committed_state": json.loads(serialize_restart(committed)),
            "arc_length_increment": None,
        }
        last_increment = getattr(solution, "last_increment", None)
        if last_increment is not None:
            restart["arc_length_increment"] = last_increment.to_payload()
        result = result.model_copy(
            update={"metadata": {**dict(result.metadata), "restart": restart}}
        )
    if not solution.succeeded or committed is None:
        return result

    recovery = adapter.recover(
        model,
        committed.displacement,
        load_factor=committed.load_factor,
        committed_state=committed.as_adapter_state(),
    )
    dof_map = adapter.dof_map(model)
    displacement_records = tuple(
        {
            "dof_index": index,
            "node_id": reference.node_id,
            "dof": reference.dof.value,
            "value": float(recovery.displacement[index]),
        }
        for index, reference in enumerate(dof_map)
    )
    reaction_records = tuple(
        {
            "dof_index": index,
            "node_id": reference.node_id,
            "dof": reference.dof.value,
            "value": float(recovery.reactions[index]),
        }
        for index, reference in enumerate(dof_map)
    )
    element_records = tuple(dict(record) for record in recovery.element_data)
    raw_fields = [
            ResultField(
                name="displacement",
                location=ResultLocation.NODE,
                basis="global-dof-order",
                records=displacement_records,
                source="adapter.recover",
            ),
            ResultField(
                name="reaction",
                location=ResultLocation.NODE,
                basis="global-dof-order",
                records=reaction_records,
                source="adapter.recover",
            ),
            ResultField(
                name="element_response",
                location=ResultLocation.ELEMENT,
                basis="element-local",
                records=element_records,
                source="adapter.recover",
            ),
        ]
    gauss_records: list[dict[str, object]] = []
    nodal_stress_samples: dict[str, list[list[float]]] = {}
    for element_record in element_records:
        points = element_record.get("gauss_points")
        node_ids = element_record.get("node_ids")
        if not isinstance(points, list):
            continue
        cauchy_samples: list[list[float]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            record = {"element_id": str(element_record["element_id"]), **point}
            gauss_records.append(record)
            cauchy = point.get("cauchy")
            if isinstance(cauchy, list) and all(
                isinstance(value, (int, float)) for value in cauchy
            ):
                cauchy_samples.append([float(value) for value in cauchy])
        if isinstance(node_ids, list) and cauchy_samples:
            element_average = [
                sum(sample[index] for sample in cauchy_samples) / len(cauchy_samples)
                for index in range(len(cauchy_samples[0]))
            ]
            for node_id in node_ids:
                nodal_stress_samples.setdefault(str(node_id), []).append(element_average)
    derived_fields: list[ResultField] = []
    if gauss_records:
        raw_fields.append(
            ResultField(
                name="gauss_point_response",
                location=ResultLocation.GAUSS_POINT,
                basis="reference-Q4-2x2",
                records=tuple(gauss_records),
                source="adapter.recover raw integration-point output",
            )
        )
        if nodal_stress_samples:
            nodal_records = tuple(
                {
                    "node_id": node_id,
                    "cauchy": [
                        sum(sample[index] for sample in samples) / len(samples)
                        for index in range(len(samples[0]))
                    ],
                }
                for node_id, samples in nodal_stress_samples.items()
            )
            derived_fields.append(
                ResultField(
                    name="nodal_smoothed_cauchy",
                    location=ResultLocation.NODE,
                    basis="global",
                    records=nodal_records,
                    is_derived=True,
                    source=(
                        "simple connected-element average of raw Gauss-point Cauchy stress; "
                        "visualization only"
                    ),
                )
            )
    post_result = PostResult(
        raw_fields=tuple(raw_fields),
        derived_fields=tuple(derived_fields),
        metadata={
            "strain_energy": float(recovery.strain_energy),
            "load_factor": float(committed.load_factor),
            "units": model.units.model_dump(mode="json"),
            **dict(recovery.metadata),
        },
    )
    return result.model_copy(update={"post_result": post_result})


__all__ = [
    "AnalysisRunner",
    "AnalysisService",
    "AnalysisStore",
    "ApiProblem",
]

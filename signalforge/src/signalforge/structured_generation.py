"""Schema-guided generation with at most one validation repair and raw audit.

No provider retries are added here. Transport/authentication errors propagate;
the existing client owns transport retries. This helper only repairs structured
response errors. Audit artifacts exclude credentials and preserve every decoded
raw response before deterministic normalization or validation.
"""
import copy
import datetime as dt
import json
from pathlib import Path
import uuid

from .llm_client import LLMError


def generate_validated(prompt, payload, config, *, schema_path, output_path,
                       generate, validate, normalize=None, preserve=None, stage="research"):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    base_prompt = (prompt + f"\n\nRequired {stage.upper()} output JSON Schema:\n"
                   + json.dumps(schema, ensure_ascii=False))
    output_path = Path(output_path)
    audit = output_path.parent / (output_path.stem + "_model_audit") / uuid.uuid4().hex
    audit.mkdir(parents=True, exist_ok=False)
    secret = getattr(config, "api_key", "")

    def write(name, value):
        encoded = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
        # Provider output or validation feedback must not echo a configured key.
        if secret:
            encoded = encoded.replace(secret, "[redacted]")
        (audit / name).write_text(encoded + "\n", encoding="utf-8")

    summary = {"stage": stage, "provider": config.provider, "model": config.model,
               "max_generation_attempts": 2, "attempts": [],
               "credential_redaction": "Configured API key redacted if present in artifacts"}
    feedback = ""
    invariants = None
    for attempt in (1, 2):
        request_prompt = base_prompt + feedback
        write(f"attempt_{attempt}_request.json", {
            "stage": stage, "provider": config.provider, "model": config.model,
            "requested_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "prompt": request_prompt, "payload": payload})
        entry = {"attempt": attempt}
        summary["attempts"].append(entry)
        try:
            raw = generate(request_prompt, payload, config)
        except LLMError as error:
            # Invalid JSON/empty model content can be repaired once; never retry
            # authentication, missing configuration, or network failures here.
            if not str(error).startswith(("Model returned invalid JSON", "Model returned an empty response")):
                entry.update(status="provider_error", error_type=type(error).__name__, error_detail=str(error).replace(secret, "[redacted]")[:300] if secret else str(error)[:300])
                write("summary.json", summary)
                raise
            raw = None
            failure = "Model returned invalid JSON or empty content. Return a JSON object."
            write(f"attempt_{attempt}_response_error.json", {"error": failure})
        else:
            write(f"attempt_{attempt}_raw_response.json", raw)
            try:
                output = copy.deepcopy(raw)
                if isinstance(output, dict):
                    output.pop("$schema", None)  # models often echo the schema URI; carries no content
                corrections = normalize(output) if normalize else []
                validate(output)
                if invariants is not None and preserve:
                    current = preserve(output)
                    if any(current.get(key) != value for key, value in invariants.items()):
                        raise ValueError("Schema repair changed an existing research conclusion or score inputs")
            except ValueError as error:
                failure = str(error)
            else:
                entry.update(status="validated", corrections=corrections)
                summary.update(status="validated", accepted_attempt=attempt)
                write("summary.json", summary)
                return output
        entry.update(status="rejected", validation_error=failure)
        write(f"attempt_{attempt}_validation.json", {"error": failure})
        summary["status"] = "rejected"
        write("summary.json", summary)
        if attempt == 2:
            # Raise a new exception to avoid retaining provider/response context.
            safe_failure = failure.replace(secret, "[redacted]") if secret else failure
            raise ValueError(safe_failure) from None
        safe_feedback = failure.replace(secret, "[redacted]") if secret else failure
        if attempt == 1 and raw is not None and preserve:
            invariants = preserve(raw)
        feedback = ("\n\nYour previous response failed validation. Return a complete JSON object "
                    "against the supplied schema. Correct only these errors; do not invent "
                    "evidence, change the research conclusion merely to pass validation, or "
                    "claim retrieval occurred. Validation errors: " + safe_feedback[:6000])
        # Do not reintroduce an unsupplied ID into the allowlisted prompt. For
        # ordinary schema failures give the actual response to edit in place.
        if raw is not None and "was not supplied" not in failure:
            previous = json.dumps(raw, ensure_ascii=False)
            if secret: previous = previous.replace(secret, "[redacted]")
            if len(previous.encode("utf-8")) <= 64_000:
                feedback += ("\nPrevious JSON to repair in place (preserve candidates, hypotheses, "
                             "recommendation and criterion scores; fix only schema errors):\n" + previous)

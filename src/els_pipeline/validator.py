"""Validator for canonical JSON records."""

import json
import logging
import re
import boto3
from typing import Dict, Any, Set, Optional
from .models import (
    NormalizedStandard,
    HierarchyLevel,
    ValidationError,
    ValidationResult,
)
from .config import Config


logger = logging.getLogger(__name__)


# JSON Schema for Canonical JSON
CANONICAL_SCHEMA = {
    "type": "object",
    "required": ["country", "state", "document", "standard", "metadata"],
    "properties": {
        "country": {"type": "string", "minLength": 2, "maxLength": 2, "pattern": "^[A-Z]{2}$"},
        "state": {"type": "string", "minLength": 1},
        "document": {
            "type": "object",
            "required": ["title", "version_year", "source_url", "age_band", "publishing_agency"],
            "properties": {
                "title": {"type": "string", "minLength": 1},
                "version_year": {"type": "integer"},
                "source_url": {"type": "string", "minLength": 1},
                "age_band": {"type": "string", "minLength": 1},
                "publishing_agency": {"type": "string", "minLength": 1},
            },
        },
        "standard": {
            "type": "object",
            "required": ["standard_id", "domain", "indicator"],
            "properties": {
                "standard_id": {"type": "string", "minLength": 1},
                "domain": {
                    "type": "object",
                    "required": ["code", "name"],
                    "properties": {
                        "code": {"type": "string", "minLength": 1},
                        "name": {"type": "string", "minLength": 1},
                    },
                },
                "strand": {
                    "oneOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "required": ["code", "name"],
                            "properties": {
                                "code": {"type": "string", "minLength": 1},
                                "name": {"type": "string", "minLength": 1},
                            },
                        },
                    ]
                },
                "sub_strand": {
                    "oneOf": [
                        {"type": "null"},
                        {
                            "type": "object",
                            "required": ["code", "name"],
                            "properties": {
                                "code": {"type": "string", "minLength": 1},
                                "name": {"type": "string", "minLength": 1},
                            },
                        },
                    ]
                },
                "indicator": {
                    "type": "object",
                    "required": ["code"],
                    "properties": {
                        "code": {"type": "string", "minLength": 1},
                        "name": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                        "description": {"oneOf": [{"type": "null"}, {"type": "string"}]},
                    },
                },
            },
        },
        "metadata": {"type": "object"},
    },
}


def _validate_schema(record: Dict[str, Any]) -> list[ValidationError]:
    """Validate record against JSON schema and collect all errors."""
    errors = []
    
    # Check top-level required fields
    for field in ["country", "state", "document", "standard", "metadata"]:
        if field not in record:
            errors.append(
                ValidationError(
                    field_path=field,
                    message=f"Missing required field: {field}",
                    error_type="missing_field",
                )
            )
        elif not record[field]:
            errors.append(
                ValidationError(
                    field_path=field,
                    message=f"Field cannot be empty: {field}",
                    error_type="invalid_type",
                )
            )
    
    # Validate country
    if "country" in record:
        if not isinstance(record["country"], str) or len(record["country"]) != 2:
            errors.append(
                ValidationError(
                    field_path="country",
                    message="country must be a two-letter ISO 3166-1 alpha-2 code",
                    error_type="invalid_type",
                )
            )
        elif not record["country"].isupper() or not record["country"].isalpha():
            errors.append(
                ValidationError(
                    field_path="country",
                    message="country must be uppercase letters only",
                    error_type="format",
                )
            )
    
    # Validate state
    if "state" in record:
        if not isinstance(record["state"], str) or len(record["state"]) == 0:
            errors.append(
                ValidationError(
                    field_path="state",
                    message="state must be a non-empty string",
                    error_type="invalid_type",
                )
            )
    
    # Validate document fields
    if "document" in record and isinstance(record["document"], dict):
        doc = record["document"]
        for field in ["title", "version_year", "source_url", "age_band", "publishing_agency"]:
            if field not in doc:
                errors.append(
                    ValidationError(
                        field_path=f"document.{field}",
                        message=f"Missing required field: document.{field}",
                        error_type="missing_field",
                    )
                )
            elif field == "version_year":
                if not isinstance(doc[field], int):
                    errors.append(
                        ValidationError(
                            field_path=f"document.{field}",
                            message=f"document.{field} must be an integer",
                            error_type="invalid_type",
                        )
                    )
            else:
                if not isinstance(doc[field], str) or len(doc[field]) == 0:
                    errors.append(
                        ValidationError(
                            field_path=f"document.{field}",
                            message=f"document.{field} must be a non-empty string",
                            error_type="invalid_type",
                        )
                    )
    elif "document" in record:
        errors.append(
            ValidationError(
                field_path="document",
                message="document must be an object",
                error_type="invalid_type",
            )
        )
    
    # Validate standard fields
    if "standard" in record and isinstance(record["standard"], dict):
        std = record["standard"]
        
        # Check standard_id
        if "standard_id" not in std:
            errors.append(
                ValidationError(
                    field_path="standard.standard_id",
                    message="Missing required field: standard.standard_id",
                    error_type="missing_field",
                )
            )
        elif not isinstance(std["standard_id"], str) or len(std["standard_id"]) == 0:
            errors.append(
                ValidationError(
                    field_path="standard.standard_id",
                    message="standard.standard_id must be a non-empty string",
                    error_type="invalid_type",
                )
            )
        
        # Check domain
        if "domain" not in std:
            errors.append(
                ValidationError(
                    field_path="standard.domain",
                    message="Missing required field: standard.domain",
                    error_type="missing_field",
                )
            )
        elif isinstance(std["domain"], dict):
            for field in ["code", "name"]:
                if field not in std["domain"]:
                    errors.append(
                        ValidationError(
                            field_path=f"standard.domain.{field}",
                            message=f"Missing required field: standard.domain.{field}",
                            error_type="missing_field",
                        )
                    )
                elif not isinstance(std["domain"][field], str) or len(std["domain"][field]) == 0:
                    errors.append(
                        ValidationError(
                            field_path=f"standard.domain.{field}",
                            message=f"standard.domain.{field} must be a non-empty string",
                            error_type="invalid_type",
                        )
                    )
        else:
            errors.append(
                ValidationError(
                    field_path="standard.domain",
                    message="standard.domain must be an object",
                    error_type="invalid_type",
                )
            )
        
        # Check strand (optional)
        if "strand" in std and std["strand"] is not None:
            if isinstance(std["strand"], dict):
                for field in ["code", "name"]:
                    if field not in std["strand"]:
                        errors.append(
                            ValidationError(
                                field_path=f"standard.strand.{field}",
                                message=f"Missing required field: standard.strand.{field}",
                                error_type="missing_field",
                            )
                        )
                    elif not isinstance(std["strand"][field], str) or len(std["strand"][field]) == 0:
                        errors.append(
                            ValidationError(
                                field_path=f"standard.strand.{field}",
                                message=f"standard.strand.{field} must be a non-empty string",
                                error_type="invalid_type",
                            )
                        )
            else:
                errors.append(
                    ValidationError(
                        field_path="standard.strand",
                        message="standard.strand must be an object or null",
                        error_type="invalid_type",
                    )
                )
        
        # Check sub_strand (optional)
        if "sub_strand" in std and std["sub_strand"] is not None:
            if isinstance(std["sub_strand"], dict):
                for field in ["code", "name"]:
                    if field not in std["sub_strand"]:
                        errors.append(
                            ValidationError(
                                field_path=f"standard.sub_strand.{field}",
                                message=f"Missing required field: standard.sub_strand.{field}",
                                error_type="missing_field",
                            )
                        )
                    elif not isinstance(std["sub_strand"][field], str) or len(std["sub_strand"][field]) == 0:
                        errors.append(
                            ValidationError(
                                field_path=f"standard.sub_strand.{field}",
                                message=f"standard.sub_strand.{field} must be a non-empty string",
                                error_type="invalid_type",
                            )
                        )
            else:
                errors.append(
                    ValidationError(
                        field_path="standard.sub_strand",
                        message="standard.sub_strand must be an object or null",
                        error_type="invalid_type",
                    )
                )
        
        # Check indicator
        if "indicator" not in std:
            errors.append(
                ValidationError(
                    field_path="standard.indicator",
                    message="Missing required field: standard.indicator",
                    error_type="missing_field",
                )
            )
        elif isinstance(std["indicator"], dict):
            # code is always required
            if "code" not in std["indicator"]:
                errors.append(
                    ValidationError(
                        field_path="standard.indicator.code",
                        message="Missing required field: standard.indicator.code",
                        error_type="missing_field",
                    )
                )
            elif not isinstance(std["indicator"]["code"], str) or len(std["indicator"]["code"]) == 0:
                errors.append(
                    ValidationError(
                        field_path="standard.indicator.code",
                        message="standard.indicator.code must be a non-empty string",
                        error_type="invalid_type",
                    )
                )
            # description is optional — may be null or empty for some age bands (e.g. PK3)
            if "description" in std["indicator"] and std["indicator"]["description"] is not None:
                if not isinstance(std["indicator"]["description"], str):
                    errors.append(
                        ValidationError(
                            field_path="standard.indicator.description",
                            message="standard.indicator.description must be a string or null",
                            error_type="invalid_type",
                        )
                    )
            # Validate optional name field (title) — must be a string or null if present
            if "name" in std["indicator"] and std["indicator"]["name"] is not None:
                if not isinstance(std["indicator"]["name"], str):
                    errors.append(
                        ValidationError(
                            field_path="standard.indicator.name",
                            message="standard.indicator.name must be a string or null",
                            error_type="invalid_type",
                        )
                    )
        else:
            errors.append(
                ValidationError(
                    field_path="standard.indicator",
                    message="standard.indicator must be an object",
                    error_type="invalid_type",
                )
            )
    elif "standard" in record:
        errors.append(
            ValidationError(
                field_path="standard",
                message="standard must be an object",
                error_type="invalid_type",
            )
        )
    
    # Validate metadata
    if "metadata" in record and not isinstance(record["metadata"], dict):
        errors.append(
            ValidationError(
                field_path="metadata",
                message="metadata must be an object",
                error_type="invalid_type",
            )
        )
    
    return errors


# --- Code-shape guard -------------------------------------------------------
#
# See `_validate_code_shape`. These are deliberately the only two constants the
# guard needs: it reads the SHAPE of a code, never any document's vocabulary.

_CODE_WHITESPACE_RE = re.compile(r"\s")

_LEVELS_ROOT_TO_LEAF = ("domain", "strand", "sub_strand", "indicator")


def _validate_code_shape(record: Dict[str, Any]) -> list[ValidationError]:
    """Reject a record whose codes are malformed, before it can reach Aurora.

    ``standard_id`` is ``{country}-{state}-{year}-{indicator_code}``, so a
    malformed indicator code IS a malformed primary key. The parser produces
    one intermittently — twice observed, with two different surface forms:

    - **California, 2026-08-13** — the structural label survived into the code:
      ``ELD.2.0.PA.Foundation 2.3.DISC`` instead of ``...PA.2.3.DISC``. 12 rows.
    - **Kentucky, 2026-08-01 and 2026-08-16** — the parent chain was dropped
      entirely: a bare ``TCPHS`` instead of ``HMW.1.1.TCPHS``, yielding the
      primary key ``US-KY-2021-TCPHS``. 4 rows and 2 rows.

    Both are sampling variance, not a code regression: the defect appears at 8
    distinct pipeline code versions, and runs over an IDENTICAL frozen input at
    temperature 0 disagree with each other (arXiv paper Task 2,
    ``paper/results/task2_20260816/heldout_evidence.json``). A prompt rule can
    lower the rate but cannot drive it to zero, and a primary key needs zero —
    the same argument that put ``derive_code_from_title`` in Python.

    **Why here and not in `parser.py`.** Three reasons, in order of importance:

    1. This is the chokepoint. ``validation_handler`` only writes an S3 record
       for a valid result, and ``persister.persist_records`` only reads keys
       listed in the validation summary — so returning an error here is what
       actually stops a bad key reaching the database. There is no bypass.
    2. It belongs to a different concern than parsing. The parser's job is to
       produce a best reading of the document; the validator's job is to refuse
       to store something structurally impossible. A guard that must hold
       regardless of which model produced the record belongs at the boundary.
    3. It keeps the paper's measurement chain intact.
       ``evaluation.eval_common.code_version_hash`` covers ``detector.py`` and
       ``parser.py`` only, and ``eval_parser`` imports ``parse_hierarchy``
       directly, so editing this file changes no recorded evaluation number and
       forces no re-run.

    Three conditions, each reading only the SHAPE of a code so that the guard
    stays document-agnostic in the sense CLAUDE.md's design direction requires
    (no per-state branch, no vocabulary, no label-word list):

    1. **No code contains whitespace.** A canonical code is a dot-separated
       path of whitespace-free segments. Whitespace means a structural label
       leaked in from the page. Note this needs no list of label words — the
       whitespace alone is the tell, which is why the guard catches
       ``Foundation 2.3`` without ever knowing the word "Foundation".
    2. **The indicator's code extends its nearest present ancestor's code.**
       Scoped to the INDICATOR level on purpose, and that scoping is
       load-bearing: a document's printed namespace may legitimately skip an
       intermediate level. Nevada codes indicators ``<domain>.<sub_strand>.PKn``
       and gives the strand its own heading identifier, so NV's sub_strand
       ``SS.ID`` does NOT extend its strand ``SS.1`` — 15 of 15 NV standards
       break the chain at that level BY DESIGN (see CLAUDE.md, "Where a printed
       code is not unique", and ``ground_truth_parser/NV.json``). Applying the
       rule at every level would reject all of Nevada. The leaf, however, is
       nested in every one of the six annotated states.
    3. **``standard_id`` ends with the indicator code.** True by construction —
       ``generate_standard_id`` derives it, and
       ``disambiguate_colliding_standards`` regenerates the id whenever it
       rewrites a code — so a violation means the two desynchronized somewhere
       and the key no longer names its own row.

    Validated against every recorded parser output before being enabled: **zero
    false positives** across all six states of the current run
    (``outputs/08-16-26``: AZ 45, CA 94, CO 48, KY 26, NV 24, TX 25 standards)
    on all three conditions, while firing on exactly the historical defects
    above. If a future document legitimately trips one of these, that is a
    finding about the canonical code namespace and belongs in a design
    discussion — do NOT add a per-state exemption here.

    WARNING: localization is partial. Task 1 asked this guard to log "raw vs
    final" so the next natural occurrence pinpoints the source component. The
    validator only ever sees the final record, so the message below carries the
    full ancestor chain, the page and the ``standard_id`` — enough to identify
    the offending row and its chunk — but not the LLM's pre-normalization code.
    Capturing that requires logging inside ``parser.py``, which would change
    ``code_version_hash`` and force a re-run of the paper's Tasks 1 and 2; do it
    when the measurement chain is next re-recorded, not before.
    """
    errors: list[ValidationError] = []
    std = record.get("standard")
    if not isinstance(std, dict):
        return errors

    # Ancestor chain, root to leaf, skipping absent levels. A missing or blank
    # code is already reported by `_validate_schema`; re-reporting it here would
    # turn one defect into two errors.
    chain: list[tuple[str, str]] = []
    for name in _LEVELS_ROOT_TO_LEAF:
        level = std.get(name)
        if not isinstance(level, dict):
            continue
        code = level.get("code")
        if isinstance(code, str) and code:
            chain.append((name, code))

    chain_repr = " -> ".join(f"{name}={code}" for name, code in chain)
    standard_id = std.get("standard_id")

    # (1) No whitespace in any code.
    for name, code in chain:
        if _CODE_WHITESPACE_RE.search(code):
            errors.append(
                ValidationError(
                    field_path=f"standard.{name}.code",
                    message=(
                        f"Code contains whitespace: {code!r}. A canonical code is a "
                        f"dot-separated path of whitespace-free segments, so whitespace "
                        f"means a structural label leaked in from the page. "
                        f"standard_id={standard_id!r}; chain: {chain_repr}"
                    ),
                    error_type="code_shape",
                )
            )

    # (2) The indicator extends its nearest present ancestor. Indicator level
    #     only — read the docstring on Nevada before widening this.
    if len(chain) >= 2 and chain[-1][0] == "indicator":
        indicator_code = chain[-1][1]
        parent_name, parent_code = chain[-2]
        if not indicator_code.startswith(f"{parent_code}."):
            errors.append(
                ValidationError(
                    field_path="standard.indicator.code",
                    message=(
                        f"Indicator code {indicator_code!r} is not nested under its "
                        f"nearest ancestor ({parent_name}={parent_code!r}), so the "
                        f"primary key would carry no namespace. "
                        f"standard_id={standard_id!r}; chain: {chain_repr}"
                    ),
                    error_type="code_shape",
                )
            )

    # (3) standard_id names its own indicator code.
    indicator = std.get("indicator")
    if isinstance(standard_id, str) and isinstance(indicator, dict):
        indicator_code = indicator.get("code")
        if (
            isinstance(indicator_code, str)
            and indicator_code
            and not standard_id.endswith(indicator_code)
        ):
            errors.append(
                ValidationError(
                    field_path="standard.standard_id",
                    message=(
                        f"standard_id {standard_id!r} does not end with its indicator "
                        f"code {indicator_code!r}; the id and the code have "
                        f"desynchronized. chain: {chain_repr}"
                    ),
                    error_type="code_shape",
                )
            )

    if errors:
        # Logged here as well as by the caller so the signature stays greppable
        # in CloudWatch regardless of how the handler reports validation errors.
        logger.warning(
            "CODE_SHAPE_GUARD blocked standard_id=%r page=%r chain=%r: %s",
            standard_id,
            (record.get("metadata") or {}).get("page_number"),
            chain_repr,
            "; ".join(e.message for e in errors),
        )

    return errors


def validate_record(
    record: Dict[str, Any],
    existing_ids: Optional[Set[tuple[str, str, int, str]]] = None,
) -> ValidationResult:
    """
    Validate a Canonical JSON record.
    
    Args:
        record: The record to validate
        existing_ids: Set of existing (country, state, version_year, standard_id) tuples for uniqueness checking
        
    Returns:
        ValidationResult with is_valid flag and any errors
    """
    errors = []
    
    # Schema validation
    schema_errors = _validate_schema(record)
    errors.extend(schema_errors)

    # Code-shape validation. Separate from the schema because the schema asks
    # "is this a non-empty string?" while this asks "is this a usable primary
    # key?" - see `_validate_code_shape` for why an intermittent parser defect
    # has to be caught at this boundary rather than fixed upstream.
    errors.extend(_validate_code_shape(record))
    
    # Uniqueness check
    if existing_ids is not None and "standard" in record and "document" in record and "country" in record and "state" in record:
        std = record.get("standard", {})
        doc = record.get("document", {})
        country = record.get("country")
        state = record.get("state")
        version_year = doc.get("version_year")
        standard_id = std.get("standard_id")
        
        if country and state and version_year and standard_id:
            record_key = (country, state, version_year, standard_id)
            if record_key in existing_ids:
                errors.append(
                    ValidationError(
                        field_path="standard.standard_id",
                        message=f"Duplicate standard_id: {standard_id} for country={country}, state={state}, year={version_year}",
                        error_type="uniqueness",
                    )
                )
    
    is_valid = len(errors) == 0
    
    return ValidationResult(
        is_valid=is_valid,
        errors=errors,
        record=record if is_valid else None,
    )


def serialize_record(
    standard: NormalizedStandard,
    document_meta: Dict[str, Any],
    page_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Serialize a NormalizedStandard to Canonical JSON format.

    Args:
        standard: The NormalizedStandard to serialize
        document_meta: Document metadata (title, source_url, age_band, publishing_agency)
        page_meta: Optional page metadata (page_number, source_text_chunk, last_verified)

    Returns:
        Canonical JSON dict
    """
    # Build standard object
    standard_obj = {
        "standard_id": standard.standard_id,
        "domain": {
            "code": standard.domain.code,
            "name": standard.domain.name,
            "description": standard.domain.description,
        },
        "strand": None,
        "sub_strand": None,
        "indicator": {
            "code": standard.indicator.code,
            "name": standard.indicator.name if standard.indicator.name else None,
            "description": standard.indicator.description,
        },
    }

    # Add strand if present
    if standard.strand:
        standard_obj["strand"] = {
            "code": standard.strand.code,
            "name": standard.strand.name,
            "description": standard.strand.description,
        }

    # Add sub_strand if present
    if standard.sub_strand:
        standard_obj["sub_strand"] = {
            "code": standard.sub_strand.code,
            "name": standard.sub_strand.name,
            "description": standard.sub_strand.description,
        }

    # Build metadata
    metadata = page_meta.copy() if page_meta else {}
    if "page_number" not in metadata:
        metadata["page_number"] = standard.source_page
    if "source_text_chunk" not in metadata:
        metadata["source_text_chunk"] = standard.source_text

    # Build canonical JSON
    canonical = {
        "country": standard.country,
        "state": standard.state,
        "document": {
            "title": document_meta["title"],
            "version_year": standard.version_year,
            "source_url": document_meta["source_url"],
            "age_band": standard.age_band or document_meta.get("age_band", "PK"),
            "publishing_agency": document_meta["publishing_agency"],
        },
        "standard": standard_obj,
        "metadata": metadata,
    }

    return canonical


def deserialize_record(json_data: Dict[str, Any]) -> NormalizedStandard:
    """
    Deserialize Canonical JSON to a NormalizedStandard object.

    Preserves descriptions for domains, strands, and sub_strands so they
    can be persisted to the database.

    Args:
        json_data: Canonical JSON dict

    Returns:
        NormalizedStandard object
    """
    std = json_data["standard"]
    doc = json_data["document"]
    meta = json_data.get("metadata", {})

    # Build hierarchy levels — preserve descriptions
    domain = HierarchyLevel(
        code=std["domain"]["code"],
        name=std["domain"]["name"],
        description=std["domain"].get("description"),
    )

    strand = None
    if std.get("strand"):
        strand = HierarchyLevel(
            code=std["strand"]["code"],
            name=std["strand"]["name"],
            description=std["strand"].get("description"),
        )

    sub_strand = None
    if std.get("sub_strand"):
        sub_strand = HierarchyLevel(
            code=std["sub_strand"]["code"],
            name=std["sub_strand"]["name"],
            description=std["sub_strand"].get("description"),
        )

    indicator = HierarchyLevel(
        code=std["indicator"]["code"],
        name=std["indicator"].get("name") or "",
        description=std["indicator"].get("description"),
    )

    # Build NormalizedStandard — age_band from document level
    return NormalizedStandard(
        standard_id=std["standard_id"],
        country=json_data["country"],
        state=json_data["state"],
        version_year=doc["version_year"],
        domain=domain,
        strand=strand,
        sub_strand=sub_strand,
        indicator=indicator,
        age_band=doc.get("age_band"),
        source_page=meta.get("page_number", 1),
        source_text=meta.get("source_text_chunk", ""),
    )


def store_validated_record(
    record: Dict[str, Any],
    s3_client=None,
) -> str:
    """
    Store a validated record to S3.
    
    Args:
        record: Validated Canonical JSON record
        s3_client: Optional boto3 S3 client (for testing)
        
    Returns:
        S3 key where the record was stored
    """
    if s3_client is None:
        s3_client = boto3.client("s3", region_name=Config.AWS_REGION)
    
    country = record["country"]
    state = record["state"]
    year = record["document"]["version_year"]
    standard_id = record["standard"]["standard_id"]
    
    # Construct S3 key with country
    s3_key = f"{country}/{state}/{year}/{standard_id}.json"
    
    # Upload to S3
    s3_client.put_object(
        Bucket=Config.S3_PROCESSED_BUCKET,
        Key=s3_key,
        Body=json.dumps(record, indent=2),
        ContentType="application/json",
    )
    
    return s3_key

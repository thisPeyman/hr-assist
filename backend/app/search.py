"""Structured-first Talent Pool search; SQL is the sole retrieval authority."""

import hashlib
import re
import unicodedata
from collections.abc import AsyncIterable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

from app.ai.actions import get_actions, get_embedding_provider
from app.config import settings
from app.models import Candidate, CandidateSearchDoc, SearchQueryCache
from app.parsing.schema import _to_strict
from app.profiles import lock_org
from app.resumes import SessionDep
from app.search_documents import normalize, refresh_document
from app.tenancy import TenantContextDep

router = APIRouter(prefix="/api/search", tags=["candidate search"])

PROTECTED = re.compile(
    r"\b(age|aged|young|younger|older|dob|birth(?:day|date)?|sex|gender|male|female|men|women|woman|man|"
    r"religion|religious|muslim|christian|jewish|ethnicity|ethnic|race|racial|nationality|"
    r"citizenship|disabled|disability|marital|married|single|pregnant|pregnancy|"
    r"health|appearance|family|سن|سنی|سالگی|ساله|تولد|جوان|جنسیت|زن|زنان|مرد|مردان|"
    r"مذهب|دین|مذهبی|مسلمان|قومیت|نژاد|ملیت|تابعیت|معلولیت|معلول|تاهل|تأهل|"
    r"متاهل|متأهل|مجرد|باردار|بارداری|بیماری|سلامت|ظاهر|خانواده)\b",
    re.I,
)
NEGATION = re.compile(
    r"\b(no|not|without|exclude|except|never|neither|non|"
    r"نه|بدون|غیر|نباشد|نباشه|نیست|نداشته|نمی|به جز)\b",
    re.I,
)
NUMBER_WORDS = re.compile(
    r"\b(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
    r"twenty|thirty|hundred|صفر|یک|دو|سه|چهار|پنج|شش|هفت|هشت|نه|ده|بیست|سی)\b",
    re.I,
)


def safe_text(value):
    value = normalize(value)
    protected_text = (
        "".join(c for c in value if unicodedata.category(c) not in {"Mn", "Cf"})
        .replace("_", " ")
        .replace("-", " ")
    )
    if PROTECTED.search(protected_text):
        raise ValueError("protected attributes are not searchable")
    return value


class SearchFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,32}$")
    field: Literal[
        "years_experience_total",
        "skill",
        "industry",
        "location",
        "name",
        "headline",
        "company",
        "stage",
        "role_status",
        "role_id",
        "owner_id",
    ]
    op: Literal["eq", "ne", "gt", "gte", "lt", "lte", "contains", "not_contains"]
    value: str = Field(min_length=1, max_length=200)
    constraint_softness: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def allowed_combination(self):
        self.value = safe_text(self.value)
        if not self.value:
            raise ValueError("empty filter value")
        if self.field == "years_experience_total":
            if self.op not in {"eq", "ne", "gt", "gte", "lt", "lte"}:
                raise ValueError("invalid numeric operator")
            if (
                not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", self.value)
                or not 0 <= float(self.value) <= 100
            ):
                raise ValueError("invalid years threshold")
        elif self.field in {"stage", "role_status", "role_id", "owner_id"}:
            if self.op not in {"eq", "ne"}:
                raise ValueError("invalid enum operator")
            if self.field.endswith("_id"):
                UUID(self.value)
            elif self.value not in (
                {"sourced", "screening", "interview", "offer", "hired", "rejected", "withdrawn"}
                if self.field == "stage"
                else {"draft", "open", "paused", "closed"}
            ):
                raise ValueError("invalid pipeline enum")
        elif self.op not in {"eq", "ne", "contains", "not_contains"}:
            raise ValueError("invalid text operator")
        return self


class SearchDSL(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filters: list[SearchFilter] = Field(default_factory=list, max_length=20)
    semantic_query: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def safe_residual(self):
        self.semantic_query = safe_text(self.semantic_query)
        if (
            re.search(r"\d|[<>≤≥+]", self.semantic_query)
            or NUMBER_WORDS.search(self.semantic_query)
            or NEGATION.search(self.semantic_query)
        ):
            raise ValueError("numbers and negations require SQL filters")
        if len({f.id for f in self.filters}) != len(self.filters):
            raise ValueError("duplicate filter ids")
        # An excluded term must never be smuggled into the vector residual.
        for f in self.filters:
            if f.op in {"ne", "not_contains"} and f.value in self.semantic_query:
                raise ValueError("negated terms cannot enter embeddings")
        return self


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str | None = Field(default=None, min_length=1, max_length=1000)
    dsl: SearchDSL | None = None
    relax: bool = False
    limit: int = Field(default=50, ge=1, le=100)

    @model_validator(mode="after")
    def one_input(self):
        if (self.query is None) == (self.dsl is None):
            raise ValueError("provide exactly query or dsl")
        if self.query is not None:
            self.query = safe_text(self.query)
            if not self.query:
                raise ValueError("empty query")
        if self.relax and self.dsl is None:
            raise ValueError("relax requires explicit DSL")
        return self


def compile_filters(filters, params):
    clauses = []
    pipeline = []
    for i, f in enumerate(filters):
        key = f"v{i}"
        params[key] = f.value
        negative = f.op in {"ne", "not_contains"}
        operator = {"eq": "=", "ne": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}.get(f.op)
        if f.field == "years_experience_total":
            params[key] = float(f.value)
            expr = f"c.years_experience_total {operator} CAST(:{key} AS double precision)"
            # Unknown years never satisfy even a negated numeric threshold.
            clauses.append(
                "c.years_experience_total IS NOT NULL AND "
                + (f"NOT ({expr})" if negative else expr)
            )
            continue
        if f.field in {"stage", "role_status", "role_id", "owner_id"}:
            column = {
                "stage": "s.kind",
                "role_status": "r.status",
                "role_id": "a.role_id",
                "owner_id": "a.owner_id",
            }[f.field]
            value = f"CAST(:{key} AS uuid)" if f.field.endswith("_id") else f":{key}"
            expr = f"{column} = {value}"
            if negative:
                clauses.append(
                    "NOT EXISTS (SELECT 1 FROM candidate_applications a "
                    "JOIN roles r ON r.id=a.role_id AND r.org_id=a.org_id "
                    "JOIN pipeline_stages s ON s.id=a.stage_id AND s.org_id=a.org_id "
                    f"WHERE a.org_id=c.org_id AND a.candidate_id=c.id AND {expr})"
                )
            else:
                pipeline.append(expr)
            continue
        # jsonb arrays are compared element-by-element, not substring JSON blobs.
        field = {"skill": "skills", "industry": "industries"}.get(f.field)
        if field:
            source = (
                f"jsonb_array_elements_text(coalesce(c.profile->'{field}','[]'::jsonb)) x(value)"
            )
            column = "x.value"
        elif f.field == "company":
            source = (
                "jsonb_array_elements(coalesce(c.profile->'work_experience','[]'::jsonb)) x(value)"
            )
            column = "x.value->>'company'"
        else:
            source = None
            column = {"name": "c.full_name", "headline": "c.headline", "location": "c.location"}[
                f.field
            ]
        # SQL normalization mirrors normalized profile/query text incl ZWNJ/digits.
        norm = (
            f"lower(btrim(regexp_replace(translate(normalize(coalesce({column},''),NFKC),"
            "'يك۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩‌','یک01234567890123456789 '),'\\s+',' ','g')))"
        )
        if f.op in {"contains", "not_contains"}:
            # strpos binds literal values: %, _, quotes never become SQL/wildcards.
            expr = f"strpos({norm},:{key}) > 0"
        else:
            expr = f"{norm} = :{key}"
        if source:
            expr = f"EXISTS (SELECT 1 FROM {source} WHERE {expr})"
        clauses.append(f"NOT ({expr})" if negative else expr)
    if pipeline:
        clauses.append(
            "EXISTS (SELECT 1 FROM candidate_applications a "
            "JOIN roles r ON r.id=a.role_id AND r.org_id=a.org_id "
            "JOIN pipeline_stages s ON s.id=a.stage_id AND s.org_id=a.org_id "
            "WHERE a.org_id=c.org_id AND a.candidate_id=c.id AND " + " AND ".join(pipeline) + ")"
        )
    return " AND ".join(f"({c})" for c in clauses) or "true"


def softest(dsl):
    choices = [f for f in dsl.filters if f.constraint_softness > 0]
    return max(choices, key=lambda f: f.constraint_softness).id if choices else None


async def retrieve(session, org_id, dsl, lexical, vector, provider, limit):
    params = {
        "org": org_id,
        "q": lexical,
        "limit": limit,
        "model": provider.model,
        "dims": provider.dimensions,
        "vector": vector,
    }
    predicates = compile_filters(dsl.filters, params)
    # Materialize the tenant + hard-filter population BEFORE every ranking leg.
    # No ANN global limit can starve small tenants or reintroduce excluded people.
    vector_leg = (
        """SELECT id, row_number() OVER (ORDER BY embedding <=> CAST(:vector AS vector),id) rank
        FROM eligible WHERE embedding IS NOT NULL AND embedding_model=:model
        AND embedding_dimensions=:dims"""
        if vector
        else "SELECT id, 0::bigint rank FROM eligible WHERE false"
    )
    query = f"""
    WITH eligible AS MATERIALIZED (
        SELECT c.id,c.full_name,c.headline,c.location,c.years_experience_total,
               d.tsv,d.normalized_name,d.embedding,d.embedding_model,d.embedding_dimensions
        FROM candidates c JOIN candidate_search_docs d ON d.candidate_id=c.id AND d.org_id=c.org_id
        WHERE c.org_id=:org AND d.org_id=:org AND {predicates}
    ), lexical AS (
        SELECT id,row_number() OVER (ORDER BY
            ts_rank_cd(tsv,plainto_tsquery('simple',:q)) DESC,
            similarity(normalized_name,:q) DESC,id) rank
        FROM eligible WHERE :q<>'' AND (tsv @@ plainto_tsquery('simple',:q)
            OR similarity(normalized_name,:q)>=0.25)
    ), semantic AS ({vector_leg}), ranked AS (
        SELECT id,sum(1.0/(60+rank)) score FROM (
            SELECT * FROM lexical UNION ALL SELECT * FROM semantic
        ) ranks GROUP BY id
    ) SELECT e.id,e.full_name,e.headline,e.location,e.years_experience_total,
             coalesce(r.score,0) score
      FROM eligible e LEFT JOIN ranked r ON r.id=e.id
      WHERE :q='' OR r.id IS NOT NULL
      ORDER BY score DESC,e.id LIMIT :limit
    """
    return (await session.execute(text(query), params)).mappings().all()


@router.post("", response_class=EventSourceResponse)
async def search(
    data: SearchRequest,
    ctx: TenantContextDep,
    session: SessionDep,
    actions: Annotated[object, Depends(get_actions)],
    provider: Annotated[object, Depends(get_embedding_provider)],
) -> AsyncIterable[ServerSentEvent]:
    warnings = []
    mode = "sql" if data.dsl else "hybrid"
    lexical = ""
    dsl = data.dsl
    if dsl is None:
        key = hashlib.sha256(
            ("v1:" + settings.search_query_model + ":" + data.query).encode()
        ).hexdigest()
        cached = await session.get(SearchQueryCache, (ctx.org.id, key))
        if cached and cached.created_at > datetime.now(UTC) - timedelta(days=1):
            dsl = SearchDSL.model_validate(cached.dsl)
        else:
            try:
                schema = SearchDSL.model_json_schema()
                payload = await actions.run(
                    "candidate_search", data.query, _to_strict(schema, defs=schema.get("$defs", {}))
                )
                dsl = SearchDSL.model_validate(payload)
                if NEGATION.search(data.query) and not any(
                    f.op in {"ne", "not_contains"} for f in dsl.filters
                ):
                    raise ValueError("query negation omitted by parser")
                if (re.search(r"\d", data.query) or NUMBER_WORDS.search(data.query)) and not any(
                    f.field == "years_experience_total" for f in dsl.filters
                ):
                    raise ValueError("numeric query omitted by parser")
            except Exception:
                dsl = SearchDSL()
                lexical, mode = data.query, "lexical"
                warnings.append("SEARCH_PARSE_FAILED")
            else:
                await session.execute(
                    insert(SearchQueryCache)
                    .values(
                        org_id=ctx.org.id,
                        query_key=key,
                        dsl=dsl.model_dump(),
                    )
                    .on_conflict_do_update(
                        index_elements=["org_id", "query_key"],
                        set_={"dsl": dsl.model_dump(), "created_at": datetime.now(UTC)},
                    )
                )
    if mode != "lexical":
        lexical = dsl.semantic_query
    relaxed = softest(dsl) if data.relax else None
    if relaxed:
        dsl = dsl.model_copy(update={"filters": [f for f in dsl.filters if f.id != relaxed]})

    async def stream():
        # This event precedes embedding/network and ranking: chips can render now.
        yield ServerSentEvent(
            data={
                "type": "filters",
                "dsl": dsl.model_dump(),
                "mode": mode,
                "warnings": warnings,
                "relaxed_filter_id": relaxed,
            }
        )
        vector = None
        if mode == "hybrid" and dsl.semantic_query:
            try:
                vector = await provider.embed(dsl.semantic_query)
            except Exception:
                yield ServerSentEvent(data={"type": "warning", "code": "SEARCH_VECTOR_FAILED"})
            else:
                missing = await session.scalar(
                    select(CandidateSearchDoc.candidate_id)
                    .where(
                        CandidateSearchDoc.org_id == ctx.org.id,
                        (CandidateSearchDoc.embedding.is_(None))
                        | (CandidateSearchDoc.embedding_model != provider.model)
                        | (CandidateSearchDoc.embedding_dimensions != provider.dimensions),
                    )
                    .limit(1)
                )
                if missing is not None:
                    yield ServerSentEvent(
                        data={"type": "warning", "code": "SEARCH_VECTOR_UNAVAILABLE"}
                    )
        try:
            async with session.begin_nested():
                rows = await retrieve(
                    session, ctx.org.id, dsl, lexical, vector, provider, data.limit
                )
        except Exception:
            if vector is None:
                raise
            yield ServerSentEvent(data={"type": "warning", "code": "SEARCH_VECTOR_FAILED"})
            rows = await retrieve(session, ctx.org.id, dsl, lexical, None, provider, data.limit)
        for row in rows:
            yield ServerSentEvent(
                data={
                    "type": "candidate",
                    "candidate": {
                        **dict(row),
                        "id": str(row["id"]),
                    },
                }
            )
        await session.commit()
        yield ServerSentEvent(
            data={
                "type": "done",
                "count": len(rows),
                "relax_filter_id": softest(dsl) if not rows else None,
            }
        )

    async for event in stream():
        yield event


class ReindexRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidate_ids: list[UUID] = Field(min_length=1, max_length=20)


@router.post("/index")
async def rebuild_index(data: ReindexRequest, ctx: TenantContextDep, session: SessionDep) -> dict:
    """Explicit bounded retry/backfill. Reading/searching never re-embeds Profiles."""
    from fastapi import HTTPException

    await lock_org(session, ctx.org.id)
    ids = set(data.candidate_ids)
    candidates = (
        await session.scalars(
            select(Candidate)
            .where(
                Candidate.org_id == ctx.org.id,
                Candidate.id.in_(ids),
            )
            .order_by(Candidate.id)
        )
    ).all()
    if len(candidates) != len(ids):
        raise HTTPException(404, "CANDIDATE_NOT_FOUND")
    result = []
    for candidate in candidates:
        await refresh_document(session, candidate)
        await session.flush()
        row = await session.get(CandidateSearchDoc, candidate.id)
        result.append(
            {
                "candidate_id": candidate.id,
                "embedding_status": row.embedding_status,
                "embedding_model": row.embedding_model,
                "embedding_dimensions": row.embedding_dimensions,
                "years_experience_total": candidate.years_experience_total,
                "computed_at": candidate.experience_computed_at,
            }
        )
    await session.commit()
    return {"items": result}

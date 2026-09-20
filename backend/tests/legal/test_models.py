from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.legal.enums import (
    AdminRole,
    AmendmentOperationType,
    AmendmentStatus,
    AuditSeverity,
    BillStatus,
    CorpusReleaseStatus,
    EmbeddingProviderKind,
    EmbeddingRunStatus,
    EvaluationDatasetKind,
    EvaluationItemKind,
    EvidenceRole,
    ExtractionCandidateStatus,
    IngestionArtifactType,
    IngestionRunStatus,
    IngestionStage,
    IngestionStepStatus,
    IngestionTaskStatus,
    InstrumentStatus,
    InstrumentType,
    LegalStatus,
    LegislativeChamber,
    LegislativeEventType,
    MessageRole,
    PageInclusionStatus,
    PageRole,
    ProvisionKind,
    ReleasePromotionStatus,
    ReviewDecisionType,
    ReviewIssueSeverity,
    ReviewIssueStatus,
    SourceTier,
    SourceUploadStatus,
    VectorIndexStatus,
    VerificationStatus,
)
from app.legal.models import (
    AdminRoleAssignment,
    Amendment,
    AmendmentOperation,
    AuditEvent,
    CandidateRevision,
    ConstitutionalBill,
    Conversation,
    ConversationMessage,
    CorpusRelease,
    CorpusReleaseEntry,
    EmbeddingProfile,
    EmbeddingRun,
    EvaluationDataset,
    EvaluationItem,
    ExtractionCandidate,
    IngestionArtifact,
    IngestionEvent,
    IngestionRun,
    IngestionStep,
    IngestionTask,
    LegalInstrument,
    LegislativeEvent,
    MessageEvidence,
    Provision,
    ProvisionVersion,
    ReleasePromotionAttempt,
    ReviewDecisionRecord,
    ReviewIssue,
    SourceDocument,
    SourcePage,
    SourceUpload,
    TransactionalOutbox,
    VectorIndex,
)
from app.models import User


def create_source_corpus(
    db: Session,
) -> tuple[LegalInstrument, SourceDocument, Provision]:
    suffix = uuid4().hex
    instrument = LegalInstrument(
        slug=f"cfrn-1999-test-{suffix}",
        title="Constitution of the Federal Republic of Nigeria 1999",
        short_title="CFRN 1999",
        instrument_type=InstrumentType.CONSTITUTION,
        jurisdiction="NG",
        year=1999,
        status=InstrumentStatus.ENACTED,
        enacted_at=date(1999, 5, 29),
        effective_at=date(1999, 5, 29),
    )
    db.add(instrument)
    db.commit()
    db.refresh(instrument)

    source = SourceDocument(
        legal_instrument_id=instrument.id,
        authority="Official Gazette",
        title="CFRN 1999 test source",
        source_url="https://example.test/cfrn-1999.pdf",
        mime_type="application/pdf",
        sha256=f"{suffix:0<64}"[:64],
        storage_backend="local",
        storage_key=f"sources/sha256/{suffix}/original.pdf",
        original_filename="cfrn-1999.pdf",
        file_size=128,
        published_at=date(1999, 5, 29),
        retrieved_at=datetime.now(UTC),
        source_tier=SourceTier.OFFICIAL,
        verification_status=VerificationStatus.VERIFIED,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    provision = Provision(
        instrument_id=instrument.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"{instrument.slug}.chapter4.section37",
        sort_key="004.037",
    )
    db.add(provision)
    db.commit()
    db.refresh(provision)

    return instrument, source, provision


def test_legal_schema_supports_anonymous_conversation_and_evidence(
    db: Session,
) -> None:
    _, source, provision = create_source_corpus(db)
    suffix = uuid4().hex
    amendment_instrument = LegalInstrument(
        slug=f"fifth-alteration-test-{suffix}",
        title="Fifth Alteration Test Act",
        instrument_type=InstrumentType.ALTERATION_ACT,
        jurisdiction="NG",
        year=2023,
        status=InstrumentStatus.ENACTED,
    )
    db.add(amendment_instrument)
    db.commit()
    db.refresh(amendment_instrument)

    amendment = Amendment(
        instrument_id=amendment_instrument.id,
        title="Fifth Alteration Test Act",
        year=2023,
        status=AmendmentStatus.ENACTED,
        source_document_id=source.id,
    )
    db.add(amendment)
    db.commit()
    db.refresh(amendment)

    version = ProvisionVersion(
        provision_id=provision.id,
        text="The privacy of citizens is protected.",
        normalized_text="the privacy of citizens is protected",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=source.id,
        text_sha256="a" * 64,
        created_by_amendment_id=amendment.id,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    operation = AmendmentOperation(
        amendment_id=amendment.id,
        target_provision_id=provision.id,
        target_version_id=version.id,
        operation_type=AmendmentOperationType.SUBSTITUTE,
        old_text="old text",
        new_text="new text",
        old_text_hash="b" * 64,
    )
    db.add(operation)

    bill_instrument = LegalInstrument(
        slug=f"state-police-bill-test-{suffix}",
        title="State Police Constitutional Bill Test",
        instrument_type=InstrumentType.BILL,
        jurisdiction="NG",
        year=2026,
        status=InstrumentStatus.PROPOSED,
    )
    db.add(bill_instrument)
    db.commit()
    db.refresh(bill_instrument)

    bill = ConstitutionalBill(
        instrument_id=bill_instrument.id,
        bill_number="HB-TEST-001",
        title="State Police Constitutional Bill Test",
        originating_chamber=LegislativeChamber.HOUSE,
        status=BillStatus.INTRODUCED,
        current_stage=BillStatus.INTRODUCED.value,
    )
    db.add(bill)
    db.commit()
    db.refresh(bill)

    event = LegislativeEvent(
        bill_id=bill.id,
        event_type=LegislativeEventType.INTRODUCED,
        event_date=date(2026, 1, 1),
        chamber=LegislativeChamber.HOUSE,
        description="Bill introduced for test purposes.",
    )
    db.add(event)

    conversation = Conversation(
        anonymous_session_id="anon-test-session",
        title="Privacy question",
        preferred_language="en",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="Privacy is protected under Section 37.",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    evidence = MessageEvidence(
        message_id=message.id,
        provision_version_id=version.id,
        evidence_role=EvidenceRole.PRIMARY,
        retrieval_rank=1,
        retrieval_score=0.98,
        citation_label="CFRN 1999, s. 37",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    assert evidence.id is not None
    assert conversation.user_id is None
    assert bill.status == BillStatus.INTRODUCED
    assert bill.status != BillStatus.ENACTED


def test_conversation_requires_user_or_anonymous_session(db: Session) -> None:
    db.add(Conversation(title="Missing owner"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_provision_versions_cannot_overlap(db: Session) -> None:
    _, source, provision = create_source_corpus(db)
    first_version = ProvisionVersion(
        provision_id=provision.id,
        text="Version one",
        normalized_text="version one",
        valid_from=date(1999, 5, 29),
        valid_until=date(2026, 1, 1),
        legal_status=LegalStatus.SUPERSEDED,
        revision_number=1,
        source_document_id=source.id,
        text_sha256="c" * 64,
    )
    overlapping_version = ProvisionVersion(
        provision_id=provision.id,
        text="Version two",
        normalized_text="version two",
        valid_from=date(2025, 1, 1),
        legal_status=LegalStatus.CURRENT,
        revision_number=2,
        source_document_id=source.id,
        text_sha256="d" * 64,
    )
    db.add(first_version)
    db.commit()
    db.add(overlapping_version)

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_ingestion_workflow_records_track_runs_steps_events_tasks_and_outbox(
    db: Session,
) -> None:
    _, source, provision = create_source_corpus(db)
    upload = SourceUpload(
        idempotency_key=f"upload-{uuid4().hex}",
        source_document_id=source.id,
        instrument_slug="cfrn-1999",
        instrument_title="Constitution of the Federal Republic of Nigeria 1999",
        instrument_year=1999,
        instrument_status=InstrumentStatus.ENACTED,
        source_title="CFRN 1999 official PDF",
        authority="Official Gazette",
        source_url="https://example.test/cfrn.pdf",
        source_tier=SourceTier.OFFICIAL,
        published_at=date(1999, 5, 29),
        retrieved_at=date(2026, 9, 10),
        original_filename="cfrn.pdf",
        mime_type="application/pdf",
        expected_size=1024,
        expected_sha256="f" * 64,
        upload_backend="local",
        quarantine_key=f"quarantine/{uuid4()}/cfrn.pdf",
        status=SourceUploadStatus.COMPLETED,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    run = IngestionRun(
        source_upload_id=upload.id,
        source_document_id=source.id,
        status=IngestionRunStatus.RUNNING,
        current_stage=IngestionStage.PROFILING,
        pipeline_config={"max_pages": 1000, "parser": "constitution"},
        total_units=10,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    step = IngestionStep(
        run_id=run.id,
        stage=IngestionStage.PROFILING,
        status=IngestionStepStatus.LEASED,
        attempt_count=1,
        lease_owner="worker-1",
        total_units=10,
        completed_units=3,
        metrics={"text_density_mean": 0.85},
        idempotency_key=f"step-{run.id}-profiling",
    )
    db.add(step)
    db.commit()
    db.refresh(step)

    event = IngestionEvent(
        run_id=run.id,
        step_id=step.id,
        sequence=1,
        event_type="stage_started",
        stage=IngestionStage.PROFILING,
        message="Profiling started",
        payload={"worker": "worker-1"},
    )
    db.add(event)
    task = IngestionTask(
        run_id=run.id,
        step_id=step.id,
        task_type=IngestionStage.PROFILING.value,
        status=IngestionTaskStatus.LEASED,
        lease_owner="worker-1",
        idempotency_key=f"task-{run.id}-profiling",
        payload={"source_document_id": str(source.id)},
    )
    db.add(task)
    outbox = TransactionalOutbox(
        aggregate_type="ingestion_run",
        aggregate_id=run.id,
        event_type="stage_started",
        idempotency_key=f"outbox-{run.id}-stage-started",
        payload={"sequence": 1},
    )
    db.add(outbox)
    db.commit()
    db.refresh(event)
    db.refresh(task)
    db.refresh(outbox)

    assert upload.status == SourceUploadStatus.COMPLETED
    assert run.current_stage == IngestionStage.PROFILING
    assert step.metrics == {"text_density_mean": 0.85}
    assert event.payload == {"worker": "worker-1"}
    assert task.status == IngestionTaskStatus.LEASED
    assert outbox.payload == {"sequence": 1}

    db.add(
        IngestionEvent(
            run_id=run.id,
            sequence=1,
            event_type="duplicate",
            message="Duplicate sequence",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_extraction_candidates_keep_review_state_out_of_canonical_tables(
    db: Session,
) -> None:
    _, source, provision = create_source_corpus(db)
    upload = SourceUpload(
        idempotency_key=f"upload-{uuid4().hex}",
        source_document_id=source.id,
        instrument_slug="cfrn-1999",
        instrument_title="Constitution of the Federal Republic of Nigeria 1999",
        instrument_year=1999,
        instrument_status=InstrumentStatus.ENACTED,
        source_title="CFRN 1999 official PDF",
        authority="Official Gazette",
        source_url="https://example.test/cfrn.pdf",
        source_tier=SourceTier.OFFICIAL,
        published_at=date(1999, 5, 29),
        retrieved_at=date(2026, 9, 10),
        original_filename="cfrn.pdf",
        mime_type="application/pdf",
        expected_size=2048,
        upload_backend="local",
        quarantine_key=f"quarantine/{uuid4()}/cfrn.pdf",
        status=SourceUploadStatus.COMPLETED,
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)

    run = IngestionRun(
        source_upload_id=upload.id,
        source_document_id=source.id,
        status=IngestionRunStatus.WAITING_FOR_REVIEW,
        current_stage=IngestionStage.REVIEW,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    page = SourcePage(
        run_id=run.id,
        source_document_id=source.id,
        page_number=37,
        role=PageRole.LEGAL_BODY,
        inclusion_status=PageInclusionStatus.INCLUDED,
        text_density=0.91,
        quality_signals={"headers_removed": False},
    )
    db.add(page)
    db.commit()
    db.refresh(page)

    artifact = IngestionArtifact(
        run_id=run.id,
        source_page_id=page.id,
        artifact_type=IngestionArtifactType.RAW_EXTRACTION,
        storage_key="artifacts/raw/page-37.json",
        sha256="1" * 64,
        mime_type="application/json",
        artifact_metadata={"extractor": "native_pdf"},
    )
    db.add(artifact)
    candidate = ExtractionCandidate(
        run_id=run.id,
        source_document_id=source.id,
        kind=ProvisionKind.SECTION,
        number="37",
        heading="Right to private and family life",
        canonical_path=f"cfrn-1999.chapter4.section37.{uuid4().hex}",
        sort_key="004.037",
        raw_text="The privacy of citizens is protected.",
        normalized_text="the privacy of citizens is protected",
        text_sha256="2" * 64,
        source_page_start=37,
        source_page_end=37,
        source_spans=[{"page": 37, "bbox": [0, 10, 200, 80]}],
        ancestor_headings=["Chapter IV", "Fundamental Rights"],
        parser_version="constitution-hierarchy-v1",
        extractor_version="native-pdf-v1",
        parser_confidence=0.99,
        extractor_confidence=0.98,
        status=ExtractionCandidateStatus.NEEDS_CORRECTION,
        blocking_issue_count=1,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    revision = CandidateRevision(
        candidate_id=candidate.id,
        revision_number=2,
        previous_text=candidate.raw_text,
        revised_text="The privacy of citizens, their homes and correspondence is protected.",
        diff="- protected.\n+ their homes and correspondence is protected.",
        reason="Matched official source wording",
    )
    issue = ReviewIssue(
        candidate_id=candidate.id,
        issue_type="missing_phrase",
        severity=ReviewIssueSeverity.BLOCKING,
        status=ReviewIssueStatus.OPEN,
        blocking=True,
        message="Candidate text omitted source phrase.",
        evidence={"page": 37},
    )
    decision = ReviewDecisionRecord(
        candidate_id=candidate.id,
        decision=ReviewDecisionType.REQUEST_CORRECTION,
        reason="Blocking omission must be fixed before materialization.",
    )
    db.add(revision)
    db.add(issue)
    db.add(decision)
    db.commit()
    db.refresh(revision)
    db.refresh(issue)
    db.refresh(decision)

    assert candidate.materialized_provision_id is None
    assert candidate.materialized_version_id is None
    assert not hasattr(provision, "ingestion_job_id")
    assert not hasattr(provision, "review_status")
    assert revision.previous_text == "The privacy of citizens is protected."
    assert issue.blocking is True
    assert decision.decision == ReviewDecisionType.REQUEST_CORRECTION


def test_release_embedding_and_vector_records_are_cumulative_by_run(
    db: Session,
) -> None:
    _, first_source, first_provision = create_source_corpus(db)
    _, second_source, second_provision = create_source_corpus(db)

    first_version = ProvisionVersion(
        provision_id=first_provision.id,
        text="First provision text",
        normalized_text="first provision text",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=first_source.id,
        text_sha256="3" * 64,
    )
    second_version = ProvisionVersion(
        provision_id=second_provision.id,
        text="Second provision text",
        normalized_text="second provision text",
        valid_from=date(1999, 5, 29),
        legal_status=LegalStatus.CURRENT,
        revision_number=1,
        source_document_id=second_source.id,
        text_sha256="4" * 64,
    )
    db.add(first_version)
    db.add(second_version)
    db.commit()
    db.refresh(first_version)
    db.refresh(second_version)

    first_run = IngestionRun(
        source_document_id=first_source.id,
        status=IngestionRunStatus.READY_TO_PUBLISH,
        current_stage=IngestionStage.VALIDATING_INDEX,
    )
    second_run = IngestionRun(
        source_document_id=second_source.id,
        status=IngestionRunStatus.READY_TO_PUBLISH,
        current_stage=IngestionStage.VALIDATING_INDEX,
    )
    db.add(first_run)
    db.add(second_run)
    db.commit()
    db.refresh(first_run)
    db.refresh(second_run)

    release = CorpusRelease(
        version=f"corpus-test-{uuid4().hex}",
        status=CorpusReleaseStatus.APPROVED,
        source_manifest_hash="5" * 64,
        validation_report={"qdrant_points": 2, "unresolved_gates": []},
    )
    db.add(release)
    db.commit()
    db.refresh(release)

    first_entry = CorpusReleaseEntry(
        release_id=release.id,
        provision_version_id=first_version.id,
        source_document_id=first_source.id,
        ingestion_run_id=first_run.id,
    )
    second_entry = CorpusReleaseEntry(
        release_id=release.id,
        provision_version_id=second_version.id,
        source_document_id=second_source.id,
        ingestion_run_id=second_run.id,
    )
    db.add(first_entry)
    db.add(second_entry)
    profile = EmbeddingProfile(
        name=f"openai-large-{uuid4().hex}",
        provider=EmbeddingProviderKind.OPENAI,
        model_name="text-embedding-3-large",
        vector_dimensions=1024,
        supports_sparse=False,
        configuration={"batch_size": 128},
        is_active=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    embedding_run = EmbeddingRun(
        release_id=release.id,
        profile_id=profile.id,
        status=EmbeddingRunStatus.SUCCEEDED,
        benchmark_dataset_version="gold-en-v1",
        recall_at_10=0.97,
        ndcg_at_10=0.93,
        cost_usd=1.25,
        p95_latency_ms=320.0,
        selected_for_release=True,
        metrics={"smoke_queries_passed": True},
    )
    db.add(embedding_run)
    db.commit()
    db.refresh(embedding_run)

    vector_index = VectorIndex(
        release_id=release.id,
        embedding_run_id=embedding_run.id,
        profile_id=profile.id,
        collection_name=f"ng_constitution_enacted_{uuid4().hex}",
        alias_name="constitution_enacted",
        index_kind="enacted",
        profile_hash="8" * 64,
        status=VectorIndexStatus.READY,
        point_count=2,
        vector_dimensions=1024,
        payload_schema_hash="6" * 64,
        checksum="7" * 64,
        validation_report={"dimensions_ok": True, "checksums_ok": True},
    )
    db.add(vector_index)
    db.commit()
    db.refresh(vector_index)

    promotion = ReleasePromotionAttempt(
        release_id=release.id,
        vector_index_id=vector_index.id,
        status=ReleasePromotionStatus.SUCCEEDED,
        target_collection_name=vector_index.collection_name,
        rollback_completed=False,
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)

    assert {first_entry.ingestion_run_id, second_entry.ingestion_run_id} == {
        first_run.id,
        second_run.id,
    }
    assert release.validation_report == {"qdrant_points": 2, "unresolved_gates": []}
    assert embedding_run.recall_at_10 == 0.97
    assert vector_index.validation_report == {
        "dimensions_ok": True,
        "checksums_ok": True,
    }
    assert promotion.status == ReleasePromotionStatus.SUCCEEDED


def test_evaluation_datasets_store_versioned_gold_and_retrieval_items(
    db: Session,
) -> None:
    _, source, provision = create_source_corpus(db)
    gold_dataset = EvaluationDataset(
        version=f"ng-constitution-gold-{uuid4().hex}",
        name="Nigerian Constitution gold provisions",
        dataset_kind=EvaluationDatasetKind.LEGAL_GRADE_EXTRACTION,
        language="en",
        jurisdiction="NG",
        source_document_id=source.id,
        content_sha256="8" * 64,
    )
    retrieval_dataset = EvaluationDataset(
        version=f"ng-constitution-retrieval-{uuid4().hex}",
        name="Nigerian Constitution retrieval benchmark",
        dataset_kind=EvaluationDatasetKind.RETRIEVAL_BENCHMARK,
        language="en",
        jurisdiction="NG",
        source_document_id=source.id,
        content_sha256="9" * 64,
    )
    db.add_all([gold_dataset, retrieval_dataset])
    db.commit()
    db.refresh(gold_dataset)
    db.refresh(retrieval_dataset)

    gold_item = EvaluationItem(
        dataset_id=gold_dataset.id,
        item_key="section-37",
        item_kind=EvaluationItemKind.GOLD_PROVISION,
        canonical_path=provision.canonical_path,
        provision_kind=ProvisionKind.SECTION,
        section_number="37",
        citation="Section 37",
        expected_text="The privacy of citizens is guaranteed.",
        source_page_start=12,
        source_page_end=12,
        source_spans=[
            {
                "page_number": 12,
                "bbox": {"x0": 36.0, "y0": 120.0, "x1": 260.0, "y1": 144.0},
            }
        ],
    )
    retrieval_item = EvaluationItem(
        dataset_id=retrieval_dataset.id,
        item_key="privacy-question",
        item_kind=EvaluationItemKind.RETRIEVAL_QUERY,
        query_text="Which section protects privacy?",
        expected_canonical_paths=[provision.canonical_path],
        item_metadata={"answer_language": "en"},
    )
    db.add_all([gold_item, retrieval_item])
    db.commit()
    db.refresh(gold_item)
    db.refresh(retrieval_item)

    assert gold_item.source_spans == [
        {
            "page_number": 12,
            "bbox": {"x0": 36.0, "y0": 120.0, "x1": 260.0, "y1": 144.0},
        }
    ]
    assert retrieval_item.expected_canonical_paths == [provision.canonical_path]
    assert retrieval_item.item_metadata == {"answer_language": "en"}

    db.add(
        EvaluationItem(
            dataset_id=gold_dataset.id,
            item_key="section-37",
            item_kind=EvaluationItemKind.GOLD_PROVISION,
            canonical_path=provision.canonical_path,
            expected_text="Duplicate key",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(
        EvaluationItem(
            dataset_id=gold_dataset.id,
            item_key="malformed-gold",
            item_kind=EvaluationItemKind.GOLD_PROVISION,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_admin_role_assignment_allows_only_one_active_role_and_audits_actions(
    db: Session,
) -> None:
    user = db.exec(select(User)).first()
    assert user is not None
    assignment = AdminRoleAssignment(
        user_id=user.id,
        role=AdminRole.LEGAL_REVIEWER,
        reason="Reviewer for ingestion test",
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)

    audit = AuditEvent(
        actor_user_id=assignment.user_id,
        action="review.override",
        entity_type="extraction_candidate",
        entity_id=uuid4(),
        severity=AuditSeverity.HIGH,
        reason="Superuser override for actor separation",
        payload={"requires_follow_up": True},
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)

    assert assignment.role == AdminRole.LEGAL_REVIEWER
    assert audit.severity == AuditSeverity.HIGH
    assert audit.payload == {"requires_follow_up": True}

    db.add(
        AdminRoleAssignment(
            user_id=assignment.user_id,
            role=AdminRole.LEGAL_REVIEWER,
            reason="Duplicate active role",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

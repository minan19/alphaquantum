from __future__ import annotations

from datetime import datetime, timezone
import re

from app.models import (
    TenderChecklistItem,
    TenderComplianceItem,
    TenderDossierResponse,
    TenderGenerationRequest,
    TenderSection,
    TenderTraceabilityItem,
    TenderValidationSummary,
)

_RE_WHITESPACE = re.compile(r"\s+")
_RE_SENTENCE_SPLIT = re.compile(r"[.\n;]+")


class TenderEngine:
    def build_dossier(self, payload: TenderGenerationRequest) -> TenderDossierResponse:
        admin_requirements = self._extract_requirements(payload.administrative_spec, source="administrative")
        technical_requirements = self._extract_requirements(payload.technical_spec, source="technical")
        extra_requirements = [
            {
                "requirement": _normalize_sentence(item),
                "source": "additional",
                "priority": "high",
            }
            for item in payload.additional_requirements
            if _normalize_sentence(item)
        ]

        requirements = self._dedupe_requirements(admin_requirements + technical_requirements + extra_requirements)
        compliance_matrix = [self._build_compliance_item(item) for item in requirements]
        attachment_checklist = self._build_attachment_checklist(payload.use_kik_baseline, compliance_matrix)
        control_checklist, traceability_matrix = self._build_control_and_traceability(
            compliance_matrix=compliance_matrix,
            attachment_checklist=attachment_checklist,
        )
        validation_summary = self._build_validation_summary(control_checklist)
        risk_notes = self._build_risk_notes(payload=payload, compliance_matrix=compliance_matrix)

        sections = self._build_sections(
            payload=payload,
            compliance_matrix=compliance_matrix,
            attachment_checklist=attachment_checklist,
            control_checklist=control_checklist,
            traceability_matrix=traceability_matrix,
            validation_summary=validation_summary,
            risk_notes=risk_notes,
        )
        dossier_markdown = self._build_markdown(
            payload=payload,
            compliance_matrix=compliance_matrix,
            attachment_checklist=attachment_checklist,
            control_checklist=control_checklist,
            traceability_matrix=traceability_matrix,
            validation_summary=validation_summary,
            risk_notes=risk_notes,
            sections=sections,
        )

        summary = (
            f"Dossier generated for {payload.institution_name} - {payload.tender_title}. "
            f"Detected {len(compliance_matrix)} requirement item(s), "
            f"{len(attachment_checklist)} attachment checkpoint(s), "
            f"{len(control_checklist)} control item(s), "
            f"and {len(risk_notes)} risk note(s). "
            f"Readiness={validation_summary.readiness_score:.2f}% "
            f"Recommendation={validation_summary.release_recommendation}."
        )

        return TenderDossierResponse(
            generated_at=datetime.now(timezone.utc).isoformat(),
            institution_name=payload.institution_name,
            tender_title=payload.tender_title,
            tender_reference=payload.tender_reference,
            executive_summary=summary,
            compliance_matrix=compliance_matrix,
            attachment_checklist=attachment_checklist,
            control_checklist=control_checklist,
            traceability_matrix=traceability_matrix,
            validation_summary=validation_summary,
            risk_notes=risk_notes,
            legal_notice=(
                "This output is a drafting and control support artifact. "
                "Final legal compliance must be validated by procurement/legal professionals."
            ),
            dossier_sections=sections,
            dossier_markdown=dossier_markdown,
        )

    def _extract_requirements(self, text: str, *, source: str) -> list[dict[str, str]]:
        requirements: list[dict[str, str]] = []
        for raw_sentence in _RE_SENTENCE_SPLIT.split(text):
            sentence = _normalize_sentence(raw_sentence)
            if len(sentence) < 12:
                continue

            lowered = sentence.lower()
            priority = "medium"
            is_requirement = False

            if any(token in lowered for token in ("zorunlu", "must", "shall", "gerekmektedir", "istenmektedir")):
                is_requirement = True
                priority = "high"
            elif any(token in lowered for token in ("uygun", "compliance", "belge", "dokuman", "teslim", "teklif")):
                is_requirement = True

            if not is_requirement:
                continue

            requirements.append(
                {
                    "requirement": sentence,
                    "source": source,
                    "priority": priority,
                }
            )

        # Fallback to avoid empty matrix when text is short or noisy.
        if not requirements:
            fallback = _normalize_sentence(text)[:180]
            if fallback:
                requirements.append(
                    {
                        "requirement": f"Review and respond to {source} specification in full scope: {fallback}",
                        "source": source,
                        "priority": "medium",
                    }
                )
        return requirements

    @staticmethod
    def _dedupe_requirements(items: list[dict[str, str]]) -> list[dict[str, str]]:
        deduped: list[dict[str, str]] = []
        seen: set[str] = set()
        for item in items:
            normalized_key = item["requirement"].strip().lower()
            if not normalized_key or normalized_key in seen:
                continue
            seen.add(normalized_key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _build_control_and_traceability(
        *,
        compliance_matrix: list[TenderComplianceItem],
        attachment_checklist: list[str],
    ) -> tuple[list[TenderChecklistItem], list[TenderTraceabilityItem]]:
        controls: list[TenderChecklistItem] = []
        control_map_by_evidence: dict[str, str] = {}
        requirement_to_control: list[tuple[TenderComplianceItem, str, str]] = []

        for idx, item in enumerate(compliance_matrix, start=1):
            control_id = f"CTRL-{idx:03d}"
            verification_method = _verification_method_for_requirement(item.requirement, item.source)
            category = "technical" if item.source == "technical" else "administrative"
            owner_role = "Technical Lead" if category == "technical" else "Procurement Lead"
            title = _control_title(item.requirement, fallback=f"{category.title()} compliance check")

            control = TenderChecklistItem(
                control_id=control_id,
                category=category,
                title=title,
                description=f"Validate and cross-check requirement: {item.requirement}",
                source_requirement=item.requirement,
                evidence_required=item.evidence_document,
                verification_method=verification_method,
                owner_role=owner_role,
                status="prepared",
                blocking=(item.priority == "high"),
                notes="Generated from compliance matrix.",
            )
            controls.append(control)
            requirement_to_control.append((item, control_id, verification_method))

        for idx, doc_name in enumerate(attachment_checklist, start=1):
            control_id = f"DOC-{idx:03d}"
            blocking = "if_required" not in doc_name
            status = "prepared" if blocking else "pending_validation"
            control = TenderChecklistItem(
                control_id=control_id,
                category="document",
                title=f"Attachment readiness: {doc_name}",
                description=f"Ensure '{doc_name}' exists, is signed/stamped where applicable, and is up to date.",
                source_requirement=None,
                evidence_required=doc_name,
                verification_method="document_presence_and_formal_validity_check",
                owner_role="Bid Coordinator",
                status=status,
                blocking=blocking,
                notes="Generated from attachment checklist.",
            )
            controls.append(control)
            if doc_name not in control_map_by_evidence:
                control_map_by_evidence[doc_name] = control_id

        controls.append(
            TenderChecklistItem(
                control_id="GATE-001",
                category="governance",
                title="Legal and procurement sign-off",
                description="Obtain legal/procurement final review and written sign-off before submission.",
                source_requirement=None,
                evidence_required="legal_procurement_signoff_record",
                verification_method="manual_approval_record_check",
                owner_role="Legal Counsel",
                status="pending_validation",
                blocking=True,
                notes="Mandatory governance gate.",
            )
        )
        controls.append(
            TenderChecklistItem(
                control_id="GATE-002",
                category="governance",
                title="Final package integrity check",
                description="Verify final bid package completeness, naming convention, and submission format.",
                source_requirement=None,
                evidence_required="final_submission_package_hash_and_manifest",
                verification_method="manual_package_integrity_check",
                owner_role="Procurement Lead",
                status="pending_validation",
                blocking=True,
                notes="Mandatory release gate before tender submission.",
            )
        )

        traceability_matrix: list[TenderTraceabilityItem] = []
        for item, requirement_control_id, verification_method in requirement_to_control:
            mapped = [requirement_control_id]
            evidence_control_id = control_map_by_evidence.get(item.evidence_document)
            if evidence_control_id and evidence_control_id not in mapped:
                mapped.append(evidence_control_id)
            traceability_matrix.append(
                TenderTraceabilityItem(
                    requirement=item.requirement,
                    source=item.source,
                    mapped_control_ids=mapped,
                    evidence_document=item.evidence_document,
                    verification_method=verification_method,
                )
            )

        return controls, traceability_matrix

    @staticmethod
    def _build_compliance_item(item: dict[str, str]) -> TenderComplianceItem:
        evidence_document = _suggest_evidence_document(
            requirement=item["requirement"],
            source=item["source"],
        )
        return TenderComplianceItem(
            requirement=item["requirement"],
            source=item["source"],
            evidence_document=evidence_document,
            status="pending",
            priority=item["priority"],
        )

    @staticmethod
    def _build_attachment_checklist(
        use_kik_baseline: bool,
        compliance_matrix: list[TenderComplianceItem],
    ) -> list[str]:
        checklist: list[str] = []
        if use_kik_baseline:
            checklist.extend(
                [
                    "trade_registry_gazette_copy",
                    "signature_circular_or_notary_authorization",
                    "tax_clearance_certificate",
                    "social_security_clearance_certificate",
                    "bid_bond_if_required",
                    "authorized_signatory_declaration",
                    "unit_price_or_cost_schedule",
                    "technical_compliance_table",
                ]
            )

        for item in compliance_matrix:
            candidate = item.evidence_document.strip()
            if candidate and candidate not in checklist:
                checklist.append(candidate)
        return checklist

    @staticmethod
    def _build_risk_notes(
        *,
        payload: TenderGenerationRequest,
        compliance_matrix: list[TenderComplianceItem],
    ) -> list[str]:
        notes: list[str] = []
        high_priority_count = sum(1 for item in compliance_matrix if item.priority == "high")
        if high_priority_count > 0:
            notes.append(
                f"{high_priority_count} high-priority requirement item(s) detected; "
                "run legal/procurement review before submission."
            )

        if payload.use_kik_baseline:
            notes.append(
                "KIK baseline checklist is a generic control set; "
                "institution-specific administrative and technical documents remain primary."
            )

        notes.append(
            "Final dossier must be reviewed against the latest institution notices, annexes, and submission format."
        )
        return notes

    @staticmethod
    def _build_validation_summary(control_checklist: list[TenderChecklistItem]) -> TenderValidationSummary:
        completed_statuses = {"prepared", "validated", "approved", "waived"}
        total_controls = len(control_checklist)
        completed_controls = sum(1 for item in control_checklist if item.status in completed_statuses)
        pending_controls = max(0, total_controls - completed_controls)
        blocking_pending_controls = sum(
            1
            for item in control_checklist
            if item.blocking and item.status not in completed_statuses
        )

        readiness_score = 100.0 if total_controls == 0 else round((completed_controls / total_controls) * 100, 2)
        if blocking_pending_controls > 0:
            recommendation = "NOT_READY"
        elif readiness_score >= 90:
            recommendation = "READY"
        else:
            recommendation = "READY_WITH_CONDITIONS"

        return TenderValidationSummary(
            total_controls=total_controls,
            completed_controls=completed_controls,
            pending_controls=pending_controls,
            blocking_pending_controls=blocking_pending_controls,
            readiness_score=readiness_score,
            release_recommendation=recommendation,
        )

    @staticmethod
    def _build_sections(
        *,
        payload: TenderGenerationRequest,
        compliance_matrix: list[TenderComplianceItem],
        attachment_checklist: list[str],
        control_checklist: list[TenderChecklistItem],
        traceability_matrix: list[TenderTraceabilityItem],
        validation_summary: TenderValidationSummary,
        risk_notes: list[str],
    ) -> list[TenderSection]:
        compliance_lines = "\n".join(
            f"- [{item.status}] ({item.priority}) {item.requirement} -> {item.evidence_document}"
            for item in compliance_matrix
        )
        attachment_lines = "\n".join(f"- {item}" for item in attachment_checklist)
        control_lines = "\n".join(
            (
                f"- {item.control_id} [{item.category}] "
                f"[{item.status}] blocking={str(item.blocking).lower()} "
                f"owner={item.owner_role} method={item.verification_method} "
                f"evidence={item.evidence_required}"
            )
            for item in control_checklist
        )
        traceability_lines = "\n".join(
            (
                f"- {item.source}: {item.requirement} -> "
                f"{', '.join(item.mapped_control_ids)} "
                f"(evidence={item.evidence_document}, verify={item.verification_method})"
            )
            for item in traceability_matrix
        )
        risk_lines = "\n".join(f"- {item}" for item in risk_notes)
        summary_line = (
            f"- total_controls={validation_summary.total_controls}\n"
            f"- completed_controls={validation_summary.completed_controls}\n"
            f"- pending_controls={validation_summary.pending_controls}\n"
            f"- blocking_pending_controls={validation_summary.blocking_pending_controls}\n"
            f"- readiness_score={validation_summary.readiness_score}\n"
            f"- release_recommendation={validation_summary.release_recommendation}"
        )

        sections: list[TenderSection] = [
            TenderSection(
                code="SEC-01",
                title="Cover and Commitment",
                content=(
                    f"{payload.company_name} hereby prepares this bid dossier draft for "
                    f"{payload.institution_name} tender '{payload.tender_title}'. "
                    "All statements and attachments are subject to legal and procurement validation."
                ),
            ),
            TenderSection(
                code="SEC-02",
                title="Administrative Compliance Matrix",
                content=compliance_lines or "- no item",
            ),
            TenderSection(
                code="SEC-03",
                title="Attachment Checklist",
                content=attachment_lines or "- no attachment",
            ),
            TenderSection(
                code="SEC-04",
                title="Risk and Control Notes",
                content=risk_lines or "- no risk note",
            ),
            TenderSection(
                code="SEC-05",
                title="Control Checklist",
                content=control_lines or "- no control item",
            ),
            TenderSection(
                code="SEC-06",
                title="Traceability Matrix",
                content=traceability_lines or "- no traceability item",
            ),
            TenderSection(
                code="SEC-07",
                title="Validation Summary",
                content=summary_line,
            ),
        ]
        return sections

    @staticmethod
    def _build_markdown(
        *,
        payload: TenderGenerationRequest,
        compliance_matrix: list[TenderComplianceItem],
        attachment_checklist: list[str],
        control_checklist: list[TenderChecklistItem],
        traceability_matrix: list[TenderTraceabilityItem],
        validation_summary: TenderValidationSummary,
        risk_notes: list[str],
        sections: list[TenderSection],
    ) -> str:
        lines: list[str] = []
        lines.append("# Tender Dossier Draft")
        lines.append("")
        lines.append(f"- Institution: **{payload.institution_name}**")
        lines.append(f"- Tender: **{payload.tender_title}**")
        if payload.tender_reference:
            lines.append(f"- Reference: **{payload.tender_reference}**")
        lines.append(f"- Company: **{payload.company_name}**")
        lines.append("")
        lines.append("## Compliance Matrix")
        lines.append("| Source | Priority | Requirement | Evidence | Status |")
        lines.append("|---|---|---|---|---|")
        for item in compliance_matrix:
            lines.append(
                f"| {item.source} | {item.priority} | {item.requirement} | "
                f"{item.evidence_document} | {item.status} |"
            )
        lines.append("")
        lines.append("## Attachment Checklist")
        for entry in attachment_checklist:
            lines.append(f"- {entry}")
        lines.append("")
        lines.append("## Control Checklist")
        lines.append("| Control ID | Category | Status | Blocking | Owner | Verification | Evidence |")
        lines.append("|---|---|---|---|---|---|---|")
        for item in control_checklist:
            lines.append(
                f"| {item.control_id} | {item.category} | {item.status} | "
                f"{str(item.blocking).lower()} | {item.owner_role} | "
                f"{item.verification_method} | {item.evidence_required} |"
            )
        lines.append("")
        lines.append("## Traceability Matrix")
        lines.append("| Source | Requirement | Controls | Evidence | Verification |")
        lines.append("|---|---|---|---|---|")
        for item in traceability_matrix:
            lines.append(
                f"| {item.source} | {item.requirement} | {', '.join(item.mapped_control_ids)} | "
                f"{item.evidence_document} | {item.verification_method} |"
            )
        lines.append("")
        lines.append("## Validation Summary")
        lines.append(f"- total_controls: **{validation_summary.total_controls}**")
        lines.append(f"- completed_controls: **{validation_summary.completed_controls}**")
        lines.append(f"- pending_controls: **{validation_summary.pending_controls}**")
        lines.append(f"- blocking_pending_controls: **{validation_summary.blocking_pending_controls}**")
        lines.append(f"- readiness_score: **{validation_summary.readiness_score}**")
        lines.append(f"- release_recommendation: **{validation_summary.release_recommendation}**")
        lines.append("")
        lines.append("## Risk Notes")
        for note in risk_notes:
            lines.append(f"- {note}")
        lines.append("")
        lines.append("## Dossier Sections")
        for section in sections:
            lines.append(f"### {section.code} - {section.title}")
            lines.append(section.content)
            lines.append("")
        return "\n".join(lines).strip()


def _normalize_sentence(text: str) -> str:
    return _RE_WHITESPACE.sub(" ", text).strip()


def _suggest_evidence_document(*, requirement: str, source: str) -> str:
    lowered = requirement.lower()
    if "imza" in lowered or "signature" in lowered:
        return "signature_circular_or_authorized_signatory_document"
    if "vergi" in lowered or "tax" in lowered:
        return "tax_clearance_certificate"
    if "sgk" in lowered or "social security" in lowered:
        return "social_security_clearance_certificate"
    if "teminat" in lowered or "bond" in lowered:
        return "bid_bond_document"
    if "teknik" in lowered or source == "technical":
        return "technical_response_matrix"
    return "administrative_compliance_statement"


def _verification_method_for_requirement(requirement: str, source: str) -> str:
    lowered = requirement.lower()
    if "imza" in lowered or "signature" in lowered:
        return "notary_and_signature_authority_check"
    if "vergi" in lowered or "tax" in lowered:
        return "tax_certificate_date_and_validity_check"
    if "sgk" in lowered or "social security" in lowered:
        return "social_security_certificate_validity_check"
    if "teminat" in lowered or "bond" in lowered:
        return "bank_bond_letter_and_amount_check"
    if "teknik" in lowered or source == "technical":
        return "technical_response_line_by_line_compliance_check"
    return "administrative_document_completeness_check"


def _control_title(requirement: str, fallback: str) -> str:
    words = requirement.split()
    if not words:
        return fallback
    short = " ".join(words[:8])
    if len(words) > 8:
        short = f"{short}..."
    return short

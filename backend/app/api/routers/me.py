"""Student endpoints: profile, recommendations with explanations, answers to conditions, saved list, updates."""
from types import SimpleNamespace

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import serializers as ser
from app.api.deps import require_profile, require_user
from app.core.config import get_settings
from app.core.ratelimit import rate_limit
from app.database import get_db
from app.models import SavedScholarship, Scholarship, StudentAnswer, StudentProfile, User
from app.schemas import AnswerIn, ProfileIn, SavedIn, SavedUpdate
from app.services import audit
from app.services.extraction import extractor, llm
from app.services.extraction.text import pdf_to_text
from app.services.recommendation import engine

router = APIRouter(prefix="/api/me", tags=["Student"])


@router.get("/profile")
def get_profile(user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    return ser.profile(p) if p else None


@router.put("/profile")
def put_profile(body: ProfileIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if p is None:
        p = StudentProfile(user_id=user.id)
        db.add(p)
    data = body.model_dump()
    if data["special_circumstances"]:
        data["special_circumstances_none"] = False
    if data.get("has_disability") is False:
        data["disability_percent"] = None
    for k, v in data.items():
        setattr(p, k, v)
    db.commit()
    return ser.profile(p)


@router.delete("/account")
def delete_account(user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Delete the account and all profile data (answers, saved items, snapshots cascade)."""
    audit.record(db, None, "account.delete", "user", user.id, {})
    db.delete(user)
    db.commit()
    return {"deleted": True}


@router.get("/recommendations")
def recommendations(profile: StudentProfile = Depends(require_profile), db: Session = Depends(get_db)):
    rec = engine.recommend(db, profile)
    rec["updates"] = engine.diff_since_acknowledged(db, profile, rec)
    return rec


@router.post("/updates/acknowledge")
def acknowledge(profile: StudentProfile = Depends(require_profile), db: Session = Depends(get_db)):
    engine.acknowledge(db, profile, engine.recommend(db, profile))
    return {"ok": True}


@router.get("/recommendations/{scholarship_id}")
def recommendation_for(scholarship_id: str, profile: StudentProfile = Depends(require_profile),
                       db: Session = Depends(get_db)):
    s = db.get(Scholarship, scholarship_id)
    if s is None or not s.is_published:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    answers = engine.answers_for(db, profile.id).get(s.id, {})
    ev = engine.best_evidence(db, [s.id]).get(s.id, {})
    result = engine.evaluate_one(profile, s, answers, ev)
    result["answers"] = answers
    return result


@router.put("/answers")
def put_answer(body: AnswerIn, profile: StudentProfile = Depends(require_profile), db: Session = Depends(get_db)):
    if db.get(Scholarship, body.scholarship_id) is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    a = db.scalar(select(StudentAnswer).where(StudentAnswer.profile_id == profile.id,
                                              StudentAnswer.scholarship_id == body.scholarship_id,
                                              StudentAnswer.criterion_key == body.criterion_key))
    if a is None:
        a = StudentAnswer(profile_id=profile.id, scholarship_id=body.scholarship_id, criterion_key=body.criterion_key)
        db.add(a)
    a.answer = body.answer
    db.commit()
    return {"ok": True}


@router.get("/saved")
def list_saved(profile: StudentProfile = Depends(require_profile), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedScholarship).where(SavedScholarship.profile_id == profile.id)
                      .order_by(SavedScholarship.created_at.desc()))
    return [{"id": r.id, "status": r.status, "notes": r.notes, "created_at": ser.iso(r.created_at),
             "updated_at": ser.iso(r.updated_at), "scholarship": engine.summary(r.scholarship)} for r in rows]


@router.post("/saved")
def add_saved(body: SavedIn, profile: StudentProfile = Depends(require_profile), db: Session = Depends(get_db)):
    if db.get(Scholarship, body.scholarship_id) is None:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    row = db.scalar(select(SavedScholarship).where(SavedScholarship.profile_id == profile.id,
                                                   SavedScholarship.scholarship_id == body.scholarship_id))
    if row is None:
        row = SavedScholarship(profile_id=profile.id, scholarship_id=body.scholarship_id)
        db.add(row)
    row.status, row.notes = body.status, body.notes
    db.commit()
    return {"id": row.id}


@router.patch("/saved/{saved_id}")
def update_saved(saved_id: str, body: SavedUpdate, profile: StudentProfile = Depends(require_profile),
                 db: Session = Depends(get_db)):
    row = db.get(SavedScholarship, saved_id)
    if row is None or row.profile_id != profile.id:
        raise HTTPException(status_code=404, detail="Not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    return {"ok": True}


@router.delete("/saved/{saved_id}")
def delete_saved(saved_id: str, profile: StudentProfile = Depends(require_profile), db: Session = Depends(get_db)):
    db.execute(delete(SavedScholarship).where(SavedScholarship.id == saved_id,
                                              SavedScholarship.profile_id == profile.id))
    db.commit()
    return {"ok": True}


_SCHOLARSHIP_DEFAULTS = dict(
    education_rule="unknown", education_levels=[], class_range=None, allowed_years=None, courses_text=None,
    fields_text=None, year_of_study_text=None, discipline_rule="unknown", disciplines=[], academic_rule="unknown",
    min_percentage=None, min_cgpa=None, cgpa_scale=10.0, academic_has_alternative=False, academic_note=None,
    income_rule="unknown", income_limit=None, income_note=None, genders=[], categories=[], category_alt_tags=[],
    category_note=None, disability_rule="none", min_disability_percent=None, eligible_states=[], conditions=[],
    amount_max_inr=None,
)


@router.post("/check-document", dependencies=[Depends(rate_limit("check_document", 10, 3600))])
async def check_document(file: UploadFile = File(...), profile: StudentProfile = Depends(require_profile)):
    """Extract rules from a scholarship PDF the student uploads and evaluate them against their profile.

    Nothing is stored. Results are AI-extracted, evidence-checked against the PDF, and NOT verified.
    """
    limit = get_settings().max_upload_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"File larger than {limit // (1024 * 1024)} MB")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")
    if not llm.status()["configured"]:
        raise HTTPException(status_code=503, detail="AI extraction is not configured on this server (no LLM key). "
                                                    "No result was generated.")
    text = pdf_to_text(data)
    if text.quality in ("empty", "needs_ocr"):
        raise HTTPException(status_code=422, detail=f"Could not read text from this PDF: {text.note}")
    try:
        result = extractor.run_extraction(text.text, f"upload:{file.filename or 'document.pdf'}")
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=f"AI extraction failed ({err.kind}): {err}") from err
    fields = {**_SCHOLARSHIP_DEFAULTS, **{k: v for k, v in result.payload.items() if k in _SCHOLARSHIP_DEFAULTS}}
    from app.services.recommendation import eligibility

    temp = SimpleNamespace(**fields)
    criteria = eligibility.evaluate(profile, temp, {})
    return {
        "label": "AI-extracted from your upload. Values without a verified quote were discarded. Not verified.",
        "extracted": result.payload, "evidence": result.evidence, "validation": result.validation,
        "criteria": criteria, "outcome": eligibility.outcome(criteria),
        "outcome_label": eligibility.OUTCOME_LABELS[eligibility.outcome(criteria)],
        "provider": result.provider, "model": result.model,
    }

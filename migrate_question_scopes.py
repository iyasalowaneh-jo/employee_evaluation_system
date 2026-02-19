"""
Migration script to add allowed_scopes column to feedback_questions table (if missing)
and backfill reasonable defaults for existing questions.
"""
from app import app
from models import db, FeedbackQuestion
import json


SCOPE_OPERATIONAL = "Operational"
SCOPE_MANAGERIAL = "Managerial"
SCOPE_STRATEGIC = "Strategic"
SCOPE_INDIRECT = "Indirect"


def _default_scopes_for_existing_question(q: FeedbackQuestion):
    """
    Backfill defaults for old questions that predate scope tagging.

    - Leadership category: Strategic + Managerial
    - Professionalism & Respect + Communication: Operational + Indirect
    - Open-ended questions: all scopes (broadly applicable)
    - Everything else: Operational-only (task / execution)
    """
    if getattr(q, "is_open_ended", False):
        return [SCOPE_OPERATIONAL, SCOPE_MANAGERIAL, SCOPE_STRATEGIC, SCOPE_INDIRECT]
    cat = (q.category or "").strip().lower()
    if cat == "leadership":
        return [SCOPE_STRATEGIC, SCOPE_MANAGERIAL]
    if cat in ("professionalism & respect", "communication"):
        # Behavioral / professionalism / basic communication: visible to Indirect
        return [SCOPE_OPERATIONAL, SCOPE_INDIRECT]
    return [SCOPE_OPERATIONAL]


def migrate_question_scopes():
    with app.app_context():
        engine = db.engine
        table = "feedback_questions"

        # Check if column exists (MySQL)
        has_column = False
        try:
            res = engine.execute(
                f"SHOW COLUMNS FROM {table} LIKE 'allowed_scopes';"
            )
            has_column = res.first() is not None
        except Exception as e:
            print(f"[WARN] Could not check column existence: {e}")

        if not has_column:
            try:
                engine.execute(
                    f"ALTER TABLE {table} ADD COLUMN allowed_scopes TEXT NOT NULL;"
                )
                print("[OK] Added allowed_scopes column")
            except Exception as e:
                print(f"[WARN] Could not add allowed_scopes column (maybe already exists): {e}")

        # Backfill values for existing rows
        updated = 0
        for q in FeedbackQuestion.query.all():
            val = getattr(q, "allowed_scopes", None)
            if not val or str(val).strip() in ("", "null", "None", "[]"):
                scopes = _default_scopes_for_existing_question(q)
                q.allowed_scopes = json.dumps(scopes)
                updated += 1
            else:
                # Ensure valid JSON list
                try:
                    parsed = json.loads(val)
                    if not isinstance(parsed, list) or len(parsed) == 0:
                        scopes = _default_scopes_for_existing_question(q)
                        q.allowed_scopes = json.dumps(scopes)
                        updated += 1
                except Exception:
                    scopes = _default_scopes_for_existing_question(q)
                    q.allowed_scopes = json.dumps(scopes)
                    updated += 1

        db.session.commit()
        print(f"[OK] Backfilled allowed_scopes for {updated} questions")


if __name__ == "__main__":
    migrate_question_scopes()


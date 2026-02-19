"""
One-off migration: ensure only 2 open-ended questions are active and global.
Deactivates any other open-ended questions so only strengths + development are asked to everyone.
"""
from app import app
from models import db, FeedbackQuestion

CANONICAL_OPEN_ENDED = [
    "What are this person's main strengths?",
    "What areas would you suggest for this person's development?",
]


def migrate_trim_open_ended():
    with app.app_context():
        all_open = FeedbackQuestion.query.filter_by(is_open_ended=True).all()
        deactivated = 0
        for q in all_open:
            if q.question_text not in CANONICAL_OPEN_ENDED:
                if q.is_active:
                    q.is_active = False
                    deactivated += 1
            else:
                # Ensure canonical ones are active and global
                if not q.is_active:
                    q.is_active = True
                if getattr(q, 'question_scope', 'global') != 'global':
                    q.question_scope = 'global'
        db.session.commit()
        if deactivated:
            print(f"[OK] Deactivated {deactivated} extra open-ended question(s). Only 2 open-ended (global) remain.")


if __name__ == '__main__':
    migrate_trim_open_ended()

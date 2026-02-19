"""
One-off migration: set question_scope to 'direct' for questions that require
direct collaboration to answer (moved from global in seed_data).
Run once if you already have feedback questions seeded before this change.
"""
from app import app
from models import db, FeedbackQuestion

QUESTIONS_TO_DIRECT = [
    'Meets agreed deadlines and commitments',
    'Takes ownership of responsibilities when needed',
    'Acknowledges mistakes and learns from them',
    'Works effectively with people from different roles or teams',
    'Supports shared goals and objectives',
    'Resolves disagreements constructively when they arise',
]


def migrate():
    with app.app_context():
        updated = 0
        for text in QUESTIONS_TO_DIRECT:
            q = FeedbackQuestion.query.filter_by(question_text=text).first()
            if q and getattr(q, 'question_scope', 'global') != 'direct':
                q.question_scope = 'direct'
                updated += 1
        db.session.commit()
        print(f"Updated question_scope to 'direct' for {updated} question(s).")


if __name__ == '__main__':
    migrate()

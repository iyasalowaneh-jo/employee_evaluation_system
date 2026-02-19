"""
Seed dummy evaluation data for the active (or latest) cycle.
Creates sample KPI evaluations and 360 feedback submissions so you can test dashboards and results.

Run: python seed_dummy_evaluations.py
"""
from app import app
from models import (
    db, Employee, EvaluationCycle, Evaluation, RandomizationLog,
    FeedbackQuestion, FeedbackEvaluation, EvaluatorScore, KPI
)
from anonymization import hash_evaluator_id
from kpi_creation import get_kpis_for_employee
from datetime import datetime
import json
import random


def _kpi_score():
    return round(random.uniform(3.0, 4.5), 1)

def _360_score():
    return round(random.uniform(3.2, 4.6), 1)

def _comment():
    return random.choice([
        "Good performance overall.",
        "Meets expectations. Reliable team member.",
        "Solid contribution this period.",
    ])


def _store_evaluator_score(evaluator_hash, evaluatee_id, cycle_id):
    """Compute and store EvaluatorScore from submitted FeedbackEvaluation rows."""
    feedbacks = FeedbackEvaluation.query.filter_by(
        evaluator_hash=evaluator_hash,
        evaluatee_id=evaluatee_id,
        cycle_id=cycle_id,
        status='submitted'
    ).all()
    scores = [f.score for f in feedbacks if f.score is not None and not getattr(f.question, 'is_open_ended', False)]
    if not scores:
        return
    final = sum(scores) / len(scores)
    existing = EvaluatorScore.query.filter_by(
        evaluator_hash=evaluator_hash,
        evaluatee_id=evaluatee_id,
        cycle_id=cycle_id
    ).first()
    if existing:
        existing.final_score = final
        existing.question_count = len(scores)
    else:
        db.session.add(EvaluatorScore(
            evaluator_hash=evaluator_hash,
            evaluatee_id=evaluatee_id,
            cycle_id=cycle_id,
            final_score=final,
            question_count=len(scores),
        ))


def seed_kpi_evaluations(cycle_id):
    """Create dummy KPI evaluations for all KPI assignments in this cycle."""
    assignments = RandomizationLog.query.filter_by(
        cycle_id=cycle_id,
        evaluation_type='kpi'
    ).all()
    created = 0
    for log in assignments:
        if not log.evaluator_id or not log.evaluatee_id:
            continue
        existing = Evaluation.query.filter_by(
            evaluator_id=log.evaluator_id,
            evaluatee_id=log.evaluatee_id,
            cycle_id=cycle_id
        ).first()
        if existing:
            continue
        evaluatee = Employee.query.get(log.evaluatee_id)
        if not evaluatee:
            continue
        kpis = get_kpis_for_employee(evaluatee, include_pending=True)
        if not kpis:
            continue
        scores = {str(k.kpi_id): _kpi_score() for k in kpis}
        db.session.add(Evaluation(
            evaluator_id=log.evaluator_id,
            evaluatee_id=log.evaluatee_id,
            cycle_id=cycle_id,
            scores=json.dumps(scores),
            comments=_comment(),
            status='approved',
            submitted_at=datetime.utcnow(),
        ))
        created += 1
    return created


def seed_360_evaluations(cycle_id, max_per_evaluatee=5):
    """
    Create dummy 360 feedback for a sample of assignments.
    max_per_evaluatee: max number of evaluators to fill in per evaluatee (so not everyone is 100% done).
    """
    assignments = RandomizationLog.query.filter_by(
        cycle_id=cycle_id,
        evaluation_type='360'
    ).all()
    # Group by evaluatee_id and cap how many we fill per evaluatee
    by_evaluatee = {}
    for log in assignments:
        if not log.evaluator_hash:
            continue
        eid = log.evaluatee_id
        if eid not in by_evaluatee:
            by_evaluatee[eid] = []
        if len(by_evaluatee[eid]) < max_per_evaluatee:
            by_evaluatee[eid].append(log)

    questions = FeedbackQuestion.query.filter_by(is_active=True).all()
    scored_questions = [q for q in questions if not getattr(q, 'is_open_ended', False)]
    open_questions = [q for q in questions if getattr(q, 'is_open_ended', False)]

    created = 0
    for evaluatee_id, logs in by_evaluatee.items():
        for log in logs:
            evaluator_hash = log.evaluator_hash
            existing_count = FeedbackEvaluation.query.filter_by(
                evaluator_hash=evaluator_hash,
                evaluatee_id=evaluatee_id,
                cycle_id=cycle_id,
                status='submitted'
            ).count()
            if existing_count > 0:
                continue
            for q in scored_questions:
                db.session.add(FeedbackEvaluation(
                    evaluator_hash=evaluator_hash,
                    evaluatee_id=evaluatee_id,
                    cycle_id=cycle_id,
                    question_id=q.question_id,
                    score=_360_score(),
                    comment=_comment() if random.random() < 0.2 else None,
                    status='submitted',
                    submitted_at=datetime.utcnow(),
                ))
                created += 1
            for q in open_questions:
                db.session.add(FeedbackEvaluation(
                    evaluator_hash=evaluator_hash,
                    evaluatee_id=evaluatee_id,
                    cycle_id=cycle_id,
                    question_id=q.question_id,
                    score=None,
                    comment=_comment(),
                    status='submitted',
                    submitted_at=datetime.utcnow(),
                ))
                created += 1
            _store_evaluator_score(evaluator_hash, evaluatee_id, cycle_id)
    return created


def main():
    with app.app_context():
        cycle = EvaluationCycle.query.filter_by(status='active').first()
        if not cycle:
            cycle = EvaluationCycle.query.order_by(EvaluationCycle.cycle_id.desc()).first()
        if not cycle:
            print("No evaluation cycle found. Create a cycle and assign evaluators first.")
            return

        print(f"Seeding dummy evaluations for cycle: {cycle.name} (id={cycle.cycle_id})")
        kpi_count = seed_kpi_evaluations(cycle.cycle_id)
        db.session.flush()
        feedback_count = seed_360_evaluations(cycle.cycle_id, max_per_evaluatee=5)
        db.session.commit()
        print(f"Done. Created {kpi_count} KPI evaluations and {feedback_count} 360 feedback rows.")


if __name__ == '__main__':
    main()

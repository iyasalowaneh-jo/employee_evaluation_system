"""
Script to add open-ended questions to the database
"""
from app import app
from models import db, FeedbackQuestion

def add_open_ended_questions():
    """Add the two open-ended questions if they don't exist"""
    with app.app_context():
        # Check if questions already exist
        existing_strengths = FeedbackQuestion.query.filter_by(
            question_text="What are this employee's main strengths?"
        ).first()
        
        existing_improvements = FeedbackQuestion.query.filter_by(
            question_text="What areas of improvement would you recommend for this employee?"
        ).first()
        
        if existing_strengths and existing_improvements:
            print("Open-ended questions already exist in database.")
            return
        
        # Add open-ended questions
        open_ended_questions = [
            {
                'category': 'Open-Ended Feedback',
                'question_text': 'What are this employee\'s main strengths?',
                'is_for_managers': False,
                'is_open_ended': True
            },
            {
                'category': 'Open-Ended Feedback',
                'question_text': 'What areas of improvement would you recommend for this employee?',
                'is_for_managers': False,
                'is_open_ended': True
            }
        ]
        
        for q_data in open_ended_questions:
            # Check if question already exists
            existing = FeedbackQuestion.query.filter_by(
                question_text=q_data['question_text']
            ).first()
            
            if not existing:
                question = FeedbackQuestion(
                    category=q_data['category'],
                    question_text=q_data['question_text'],
                    is_for_managers=q_data['is_for_managers'],
                    is_open_ended=q_data['is_open_ended'],
                    is_active=True
                )
                db.session.add(question)
                print(f"Added question: {q_data['question_text'][:50]}...")
            else:
                # Update existing question to mark it as open-ended
                existing.is_open_ended = True
                existing.category = q_data['category']
                print(f"Updated existing question: {q_data['question_text'][:50]}...")
        
        db.session.commit()
        print("\nOpen-ended questions added successfully!")

if __name__ == '__main__':
    add_open_ended_questions()

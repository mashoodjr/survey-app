from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField, RadioField, BooleanField
from wtforms.validators import DataRequired, Email, Length
import json
import datetime
from textblob import TextBlob
from collections import defaultdict

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://survey_user:survey_password@localhost/survey_db'  # Update with your credentials
db = SQLAlchemy(app)

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    age_group = db.Column(db.String(20), nullable=False)
    gender = db.Column(db.String(20), nullable=False)
    experience = db.Column(db.String(20), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    feedback = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    last_updated = db.Column(db.DateTime, onupdate=db.func.now())
    is_draft = db.Column(db.Boolean, default=False)
    draft_id = db.Column(db.String(36))  # For saving drafts

class SurveyForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Email()])
    age_group = SelectField('Age Group', choices=[
        ('18-24', '18-24'),
        ('25-34', '25-34'),
        ('35-44', '35-44'),
        ('45-54', '45-54'),
        ('55+', '55+')
    ], validators=[DataRequired()])
    gender = SelectField('Gender', choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('prefer_not_to_say', 'Prefer not to say')
    ], validators=[DataRequired()])
    experience = RadioField('How often do you use our service?', choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('occasionally', 'Occasionally'),
        ('first_time', 'First time')
    ], validators=[DataRequired()])
    rating = SelectField('Overall Rating', choices=[
        ('1', '1 - Very Poor'),
        ('2', '2 - Poor'),
        ('3', '3 - Average'),
        ('4', '4 - Good'),
        ('5', '5 - Excellent')
    ], validators=[DataRequired()])
    feedback = TextAreaField('Additional Feedback', validators=[DataRequired()], 
                           render_kw={'rows': 5})
    submit = SubmitField('Next')
    save_draft = SubmitField('Save Draft')
    skip = SubmitField('Skip Question')

class SummaryForm(FlaskForm):
    submit = SubmitField('Submit')
    back = SubmitField('Back')
    save_draft = SubmitField('Save as Draft')

def analyze_sentiment(text):
    """Analyze sentiment of feedback text"""
    blob = TextBlob(text)
    return {
        'polarity': blob.sentiment.polarity,
        'subjectivity': blob.sentiment.subjectivity,
        'sentiment': 'positive' if blob.sentiment.polarity > 0 else 
                    'negative' if blob.sentiment.polarity < 0 else 'neutral'
    }

def get_survey_statistics():
    total_responses = Survey.query.count()
    if total_responses == 0:
        return {
            'total_responses': 0,
            'average_rating': 0,
            'rating_distribution': {
                '1': 0,
                '2': 0,
                '3': 0,
                '4': 0,
                '5': 0
            },
            'age_distribution': {
                '18-24': 0,
                '25-34': 0,
                '35-44': 0,
                '45-54': 0,
                '55+': 0
            },
            'gender_distribution': {
                'male': 0,
                'female': 0,
                'other': 0,
                'prefer_not_to_say': 0
            },
            'sentiment_distribution': {
                'positive': 0,
                'negative': 0,
                'neutral': 0
            },
            'response_time': {
                'average': 0,
                'fastest': None,
                'slowest': None
            }
        }

    # Calculate statistics
    stats = {
        'total_responses': total_responses,
        'average_rating': db.session.query(db.func.avg(Survey.rating)).scalar(),
        'rating_distribution': {},
        'age_distribution': {},
        'gender_distribution': {},
        'sentiment_distribution': defaultdict(int),
        'response_time': {
            'average': 0,
            'fastest': None,
            'slowest': None
        }
    }

    # Rating distribution
    ratings = db.session.query(Survey.rating, db.func.count())\
        .group_by(Survey.rating).all()
    stats['rating_distribution'] = {str(r[0]): r[1] for r in ratings}

    # Age distribution
    age_groups = db.session.query(Survey.age_group, db.func.count())\
        .group_by(Survey.age_group).all()
    stats['age_distribution'] = {str(g[0]): g[1] for g in age_groups}

    # Gender distribution
    genders = db.session.query(Survey.gender, db.func.count())\
        .group_by(Survey.gender).all()
    stats['gender_distribution'] = {str(g[0]): g[1] for g in genders}

    # Sentiment analysis
    surveys = Survey.query.all()
    for survey in surveys:
        sentiment = analyze_sentiment(survey.feedback)
        stats['sentiment_distribution'][sentiment['sentiment']] += 1

    # Response time analysis
    response_times = []
    for survey in surveys:
        if survey.last_updated:
            response_time = (survey.last_updated - survey.created_at).total_seconds()
            response_times.append(response_time)

    if response_times:
        stats['response_time']['average'] = sum(response_times) / len(response_times)
        stats['response_time']['fastest'] = min(response_times)
        stats['response_time']['slowest'] = max(response_times)

    return stats

@app.route('/')
@app.route('/survey', methods=['GET', 'POST'])
def survey():
    form = SurveyForm()
    
    # Check if there's a saved draft
    draft_id = session.get('draft_id')
    if draft_id:
        draft = Survey.query.filter_by(draft_id=draft_id, is_draft=True).first()
        if draft:
            form.name.data = draft.name
            form.email.data = draft.email
            form.age_group.data = draft.age_group
            form.gender.data = draft.gender
            form.experience.data = draft.experience
            form.rating.data = str(draft.rating)
            form.feedback.data = draft.feedback

    if form.validate_on_submit():
        if form.save_draft.data:
            # Save as draft
            draft = Survey(
                name=form.name.data,
                email=form.email.data,
                age_group=form.age_group.data,
                gender=form.gender.data,
                experience=form.experience.data,
                rating=form.rating.data,
                feedback=form.feedback.data,
                is_draft=True,
                draft_id=str(datetime.datetime.now().timestamp())
            )
            db.session.add(draft)
            db.session.commit()
            session['draft_id'] = draft.draft_id
            flash('Survey saved as draft. You can resume it later.', 'info')
            return redirect(url_for('survey'))
        else:
            # Continue to summary
            session_data = {
                'name': form.name.data,
                'email': form.email.data,
                'age_group': form.age_group.data,
                'gender': form.gender.data,
                'experience': form.experience.data,
                'rating': form.rating.data,
                'feedback': form.feedback.data
            }
            return redirect(url_for('summary', data=json.dumps(session_data)))

    return render_template('survey.html', form=form)

@app.route('/summary', methods=['GET', 'POST'])
def summary():
    data = request.args.get('data')
    if not data:
        flash('Please complete the survey first!', 'error')
        return redirect(url_for('survey'))

    session_data = json.loads(data)
    form = SummaryForm()
    
    if form.validate_on_submit():
        if form.submit.data:
            # Save complete survey
            new_survey = Survey(
                name=session_data['name'],
                email=session_data['email'],
                age_group=session_data['age_group'],
                gender=session_data['gender'],
                experience=session_data['experience'],
                rating=session_data['rating'],
                feedback=session_data['feedback']
            )
            db.session.add(new_survey)
            db.session.commit()
            flash('Thank you for your feedback!', 'success')
            return redirect(url_for('thank_you'))
        elif form.back.data:
            return redirect(url_for('survey'))
        elif form.save_draft.data:
            # Save as draft
            draft = Survey(
                name=session_data['name'],
                email=session_data['email'],
                age_group=session_data['age_group'],
                gender=session_data['gender'],
                experience=session_data['experience'],
                rating=session_data['rating'],
                feedback=session_data['feedback'],
                is_draft=True,
                draft_id=str(datetime.datetime.now().timestamp())
            )
            db.session.add(draft)
            db.session.commit()
            session['draft_id'] = draft.draft_id
            flash('Survey saved as draft. You can resume it later.', 'info')
            return redirect(url_for('survey'))

    return render_template('summary.html', form=form, data=session_data)

@app.route('/thank-you')
def thank_you():
    return render_template('thank_you.html')

@app.route('/results')
def results():
    surveys = Survey.query.filter_by(is_draft=False).order_by(Survey.created_at.desc()).all()
    stats = get_survey_statistics()
    return render_template('results.html', surveys=surveys, stats=stats)

@app.route('/api/stats')
def api_stats():
    stats = get_survey_statistics()
    return jsonify(stats)

@app.route('/api/validate-email', methods=['POST'])
def validate_email():
    data = request.json
    email = data.get('email')
    if not email:
        return jsonify({'valid': False, 'message': 'Email is required'}), 400
    
    if Survey.query.filter_by(email=email).first():
        return jsonify({'valid': False, 'message': 'This email has already submitted a survey'}), 400
    
    return jsonify({'valid': True})

@app.route('/api/save-progress', methods=['POST'])
def save_progress():
    data = request.json
    draft_id = session.get('draft_id')
    
    if draft_id:
        draft = Survey.query.filter_by(draft_id=draft_id, is_draft=True).first()
        if draft:
            draft.name = data.get('name', draft.name)
            draft.email = data.get('email', draft.email)
            draft.age_group = data.get('age_group', draft.age_group)
            draft.gender = data.get('gender', draft.gender)
            draft.experience = data.get('experience', draft.experience)
            draft.rating = data.get('rating', draft.rating)
            draft.feedback = data.get('feedback', draft.feedback)
            db.session.commit()
            return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'No draft found'}), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)

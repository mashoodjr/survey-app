# Survey Application

A simple survey form application built with Flask and PostgreSQL.

## Setup Instructions

1. Create a PostgreSQL database:
```bash
createdb survey_db
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Update the database configuration in `app.py`:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://username:password@localhost/survey_db'
```

4. Run the application:
```bash
python app.py
```

5. Access the application:
- Survey form: http://localhost:5000/
- Results: http://localhost:5000/results

## Features

- User-friendly survey form with name, email, and feedback fields
- Data stored in PostgreSQL database
- Results page showing all submitted surveys
- Bootstrap styling for a modern look
- Flash messages for user feedback


# Authors
- [Samuel Niwagila](https://github.com/mashoodjr)

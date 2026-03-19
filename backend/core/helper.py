import re
import datetime 

def validate_date_format(date_string: str) -> str:
    """Custom type validator for YYYY-MM-DD format."""
    if date_string is None:
        return 

    return datetime.datetime.strptime(date_string, '%Y-%m-%d').date()

def validate_age(dob: datetime.datetime) -> bool:
    today = datetime.date.today()

    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    return False if age < 18 else True


# app/utils/experience_calculator.py
from datetime import datetime
from dateutil import parser as date_parser
from typing import List, Optional
import re

def calculate_years_of_experience(work_experience: List) -> Optional[float]:
    """
    Calculate total years of professional experience from work history.
    
    Args:
        work_experience: List of WorkExperience objects with start_date and end_date
        
    Returns:
        Total years of experience (float), or None if cannot be calculated
    """
    if not work_experience:
        return None
    
    total_months = 0
    
    for job in work_experience:
        try:
            # Get start and end dates
            start_date_str = job.start_date if hasattr(job, 'start_date') else job.get('start_date')
            end_date_str = job.end_date if hasattr(job, 'end_date') else job.get('end_date')
            
            if not start_date_str:
                continue
                
            # Parse start date
            start_date = parse_date_flexible(start_date_str)
            if not start_date:
                continue
            
            # Parse end date (or use current date if "Present")
            if not end_date_str or end_date_str.lower() in ['present', 'current', 'now']:
                end_date = datetime.now()
            else:
                end_date = parse_date_flexible(end_date_str)
                if not end_date:
                    continue
            
            # Calculate months for this job
            months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
            total_months += max(months, 0)  # Ensure non-negative
            
        except Exception as e:
            # Skip this job if date parsing fails
            print(f"   ⚠️  Could not parse dates for job: {e}")
            continue
    
    if total_months == 0:
        return None
    
    # Convert to years (round to 1 decimal)
    years = round(total_months / 12, 1)
    return years


def parse_date_flexible(date_str: str) -> Optional[datetime]:
    """
    Parse date strings flexibly (handles various formats).
    
    Supported formats:
    - "January 2021", "Jan 2021"
    - "2021-01", "01/2021"
    - "2021"
    - "Q1 2021"
    """
    if not date_str:
        return None
    
    date_str = date_str.strip()
    
    try:
        # Try standard parsing first
        return date_parser.parse(date_str, fuzzy=True)
    except:
        pass
    
    # Try just year (assume January)
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if year_match:
        year = int(year_match.group(0))
        return datetime(year, 1, 1)
    
    return None


def format_experience_years(years: float) -> str:
    """Format years of experience for display"""
    if years is None:
        return "Not specified"
    
    if years < 1:
        months = int(years * 12)
        return f"{months} months"
    elif years == 1:
        return "1 year"
    else:
        # Show 1 decimal for < 10 years, round for >= 10
        if years < 10:
            return f"{years:.1f} years"
        else:
            return f"{int(round(years))} years"

# simply.py
# A minimal script to insert events from an ICS feed into daily markdown notes.

import os
import re
import datetime
import requests
import icalendar  # type: ignore
from zoneinfo import ZoneInfo
from datetime import timedelta

# Simple constants
CALENDAR_HEADER = "### Calendar\n"
TIMEZONE = ZoneInfo("America/New_York")

def remove_calendar_section(content):
    """
    Remove an existing calendar section from note content.
    Returns (cleaned_content, removed_section_count).
    """
    lines = content.splitlines()
    new_lines = []
    in_calendar_section = False
    removed_sections = 0

    for line in lines:
        # Look for a header that has "calendar" in it
        if (
            line.strip().lower().startswith(("#", "##", "###"))
            and "calendar" in line.lower()
        ):
            in_calendar_section = True
            removed_sections += 1
            continue

        if in_calendar_section:
            # Stop skipping lines if we reach another header
            if line.strip().startswith(("#", "##", "###")):
                in_calendar_section = False
                new_lines.append(line)
        else:
            new_lines.append(line)

    return "\n".join(new_lines), removed_sections

def insert_calendar_section(content, events_markdown):
    """
    Insert the new calendar section (CALENDAR_HEADER + events) at the top.
    """
    return CALENDAR_HEADER + events_markdown + "\n" + content

def extract_date_from_filename(filename):
    """
    Parse a date from a filename with the pattern 'MM-DD-YYYY'.
    Returns a date object or None if not found.
    """
    pattern = re.compile(r"(\d{2})-(\d{2})-(\d{4})")
    match = pattern.search(filename)
    if not match:
        return None
    month, day, year = match.groups()
    try:
        return datetime.date(int(year), int(month), int(day))
    except ValueError:
        return None

def format_events_as_markdown(events):
    """
    Takes a list of (summary, start_time, end_time) tuples and returns
    a simple markdown list of events.
    """
    if not events:
        return "_No events today_\n"

    lines = []
    for summary, start, end in events:
        # Check for all-day by comparing hours/mins
        if start.hour == 0 and start.minute == 0 and end.hour == 0 and end.minute == 0:
            lines.append(f"- {summary} (All-day)")
        else:
            start_str = start.strftime("%H:%M")
            end_str = end.strftime("%H:%M")
            lines.append(f"- {start_str} - {end_str} {summary}")

    return "\n".join(lines) + "\n"

def fetch_events_for_date(ics_url, target_date):
    """
    Fetch events from a single ICS URL, filter by the target_date.
    Returns a list of (summary, start_time, end_time).
    """
    if not ics_url:
        return []

    try:
        response = requests.get(ics_url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch ICS: {e}")
        return []

    cal = icalendar.Calendar.from_ical(response.content)
    day_start = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=TIMEZONE)
    day_end = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=TIMEZONE)

    events_list = []

    for component in cal.walk("vevent"):
        summary = component.get("SUMMARY", "No Title")
        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND") or dtstart

        if not dtstart:
            continue

        start_time = dtstart.dt
        end_time = dtend.dt if dtend else start_time

        # Convert date objects to datetime if necessary
        if isinstance(start_time, datetime.date) and not isinstance(start_time, datetime.datetime):
            start_time = datetime.datetime.combine(start_time, datetime.time.min, tzinfo=TIMEZONE)
        if isinstance(end_time, datetime.date) and not isinstance(end_time, datetime.datetime):
            end_time = datetime.datetime.combine(end_time, datetime.time.min, tzinfo=TIMEZONE)

        # Force timezone if missing
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=TIMEZONE)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=TIMEZONE)

        # Check if this event occurs on the target day
        # All-day events often span from midnight to midnight
        # so we check overlap with day_start/day_end.
        if not (end_time < day_start or start_time > day_end):
            events_list.append((str(summary), start_time, end_time))

    return events_list

def main():
    ics_url = os.getenv("MY_SIMPLE_ICS_URL", "")  # or hardcode a URL here
    notes_directory = "./notes"

    for root, dirs, files in os.walk(notes_directory):
        for filename in files:
            if not filename.lower().endswith(".md"):
                continue

            note_date = extract_date_from_filename(filename)
            if not note_date:
                continue

            # Load note
            file_path = os.path.join(root, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Remove old calendar section
            content_clean, removed_count = remove_calendar_section(content)

            # Fetch new events
            day_events = fetch_events_for_date(ics_url, note_date)
            events_md = format_events_as_markdown(day_events)

            # Insert new calendar section
            updated_content = insert_calendar_section(content_clean, events_md)

            # Save
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(updated_content)

if __name__ == "__main__":
    main()

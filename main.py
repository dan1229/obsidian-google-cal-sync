import logging
import os
import re
import requests
import datetime
from zoneinfo import ZoneInfo  # Add this import at the top
from datetime import timedelta
from recurring_ical_events import of  # type: ignore
import icalendar  # type: ignore

# -------------------------------------------------------------------
#
# UPDATE CALENDAR
#
# This script is used to update the calendar section in daily notes with
# events from various calendars (e.g. Google Calendar).
# It is meant to update the calendar section in daily notes with events,
# remove stale events, and optionally add links (if available).
#
# -------------------------------------------------------------------


# -------------------------------------------------------------------
# CONSTANTS AND LOGGING
# -------------------------------------------------------------------

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# This is the header that will be added to and searched for in the top
# of the calendar section in the daily note
HEADER_CALENDAR_EVENTS = "### Calendar Events\n"

CALENDAR_LABELS = {
    "personal": "(Personal 🗓️)",
    "events": "(Events 🎊)",
    "us_holidays": "(US Holidays 🇺🇸)",
    "jewish_holidays": "(Jewish Holidays ✡️)",
}

EVENT_KEYWORDS = {
    # Work & Meetings
    "meeting": "💼",
    "call": "📞",
    "zoom": "🎥",
    "interview": "🤝",
    "deadline": "⏰",
    "presentation": "📊",
    "conference": "🎤",
    "workshop": "👨‍🏫",
    "standup": "🌅",
    "review": "👀",
    "1:1": "👥",
    "sync": "🔄",
    # Food & Drinks
    "lunch": "🍽️",
    "dinner": "🍴",
    "breakfast": "🍳",
    "brunch": "🥞",
    "coffee": "☕",
    "drinks": "🍻",
    "happy hour": "🍷",
    "restaurant": "🍽️",
    # Health & Wellness
    "doctor": "👨‍⚕️",
    "dentist": "🦷",
    "therapy": "🧠",
    "gym": "💪",
    "workout": "🏋️",
    "yoga": "🧘",
    "meditation": "🧘‍♂️",
    "massage": "💆",
    "appointment": "🏥",
    # Travel & Transportation
    "flight": "✈️",
    "travel": "🧳",
    "vacation": "🏖️",
    "trip": "🗺️",
    "train": "🚂",
    "bus": "🚌",
    "airport": "✈️",
    "hotel": "🏨",
    # Education & Learning
    "study": "📚",
    "class": "📓",
    "lecture": "👨‍🏫",
    "homework": "✏️",
    "exam": "📝",
    "training": "🎓",
    "webinar": "💻",
    "course": "📖",
    # Entertainment & Social
    "game": "🎮",
    "movie": "🎬",
    "concert": "🎵",
    "theater": "🎭",
    "show": "🎪",
    "party": "🎉",
    "birthday": "🎂",
    "celebration": "🎊",
    "festival": "🎪",
    "music": "🎼",
    "dance": "💃",
    "date": "❤️",
    # Shopping & Errands
    "shopping": "🛍️",
    "grocery": "🛒",
    "errands": "📝",
    "pickup": "📦",
    "delivery": "📬",
    "store": "🏪",
    # Home & Personal
    "cleaning": "🧹",
    "laundry": "👕",
    "maintenance": "🔧",
    "repair": "🔨",
    "moving": "📦",
    "packing": "📦",
    # Holidays & Religion
    "holiday": "🎊",
    "christmas": "🎄",
    "hanukkah": "🕎",
    "passover": "✡️",
    "easter": "🐰",
    "thanksgiving": "🦃",
    "new year": "🎆",
    "prayer": "🙏",
    "service": "⛪",
    # Misc
    "reminder": "⏰",
    "todo": "✅",
    "important": "❗",
    "urgent": "‼️",
}


# -------------------------------------------------------------------
# 1. ICS FETCHING / PARSING
# -------------------------------------------------------------------


def clean_event(
    event, calendar_type, start_datetime, end_datetime, target_date, events_for_date
):
    tz = ZoneInfo("America/New_York")

    # Handle recurring events by checking if this instance occurs on target_date
    try:
        target_start = datetime.datetime.combine(
            target_date, datetime.time.min, tzinfo=tz
        )
        target_end = datetime.datetime.combine(
            target_date, datetime.time.max, tzinfo=tz
        )

        if hasattr(event, "recurring"):
            recurring_instances = of(event).at(target_start)
            if not any(
                inst.begin <= target_end and inst.end >= target_start
                for inst in recurring_instances
            ):
                return events_for_date
    except Exception as e:
        logger.error(f"Error processing recurring event: {str(event)}.\n{e}")
        return events_for_date

    # Ensure event times are timezone-aware
    try:
        event_start = event.get("dtstart").dt
        event_end = event.get("dtend").dt if event.get("dtend") else event_start

        if isinstance(event_start, datetime.date) and not isinstance(
            event_start, datetime.datetime
        ):
            event_start = datetime.datetime.combine(event_start, datetime.time.min)
        if isinstance(event_end, datetime.date) and not isinstance(
            event_end, datetime.datetime
        ):
            event_end = datetime.datetime.combine(event_end, datetime.time.min)
    except (AttributeError, KeyError) as e:
        logger.error(f"Event missing begin/end time: {str(event)}.\n{e}")
        return events_for_date

    if event_start.tzinfo is None:
        event_start = event_start.replace(tzinfo=tz)
    if event_end.tzinfo is None:
        event_end = event_end.replace(tzinfo=tz)

    # Check if it's an all-day event
    try:
        is_all_day = getattr(event, "all_day", False) or (
            (event_end - event_start).days >= 1
            and event_start.hour == 0
            and event_start.minute == 0
            and event_end.hour == 0
            and event_end.minute == 0
        )
    except (TypeError, AttributeError) as e:
        logger.error(f"Could not determine if all-day event: {event.name}.\n{e}")
        return events_for_date

    try:
        if is_all_day:
            start_date = event_start.date()
            end_date = event_end.date() - timedelta(days=1)
            if start_date <= target_date <= end_date:
                events_for_date.append((event, calendar_type))
        else:
            if not (event_end < start_datetime or event_start > end_datetime):
                events_for_date.append((event, calendar_type))
    except (TypeError, ValueError) as e:
        logger.error(f"Could not process event dates: {event.name}.\n{e}")

    return events_for_date


def get_calendar_label(calendar_type):
    """Returns the formatted calendar label with emoji for the given calendar type."""
    return CALENDAR_LABELS.get(calendar_type, "(Other 🤷)")


def fetch_events_for_date(ics_urls_with_types, target_date):
    """
    Fetches and processes events, properly handling recurring events.
    Returns a list of (expanded_event, calendar_type) tuples.
    """
    logger.info(f"Fetching events for date: {target_date}")
    events_for_date = []
    tz = ZoneInfo("America/New_York")

    start_datetime = datetime.datetime.combine(
        target_date, datetime.time.min, tzinfo=tz
    )
    end_datetime = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=tz)

    # Look back 1 year and forward 2 years from target date for recurring events
    recurring_start = start_datetime - timedelta(days=365)
    recurring_end = start_datetime + timedelta(days=730)

    for ics_url, calendar_type in ics_urls_with_types:
        if not ics_url:
            continue

        try:
            logger.info(f"Fetching calendar from: {ics_url[:50]}...")
            resp = requests.get(ics_url)
            resp.raise_for_status()
        except requests.RequestException as e:
            calendar_name = get_calendar_label(calendar_type)
            logger.error(f"Request failed for {calendar_name}.\n{e}")
            continue

        cal = icalendar.Calendar.from_ical(resp.content)

        # Process each 'regular' event
        for event in cal.events:
            events_for_date = clean_event(
                event,
                calendar_type,
                start_datetime,
                end_datetime,
                target_date,
                events_for_date,
            )

        # Handle recurring events with proper date range
        events_recurring = of(cal).between(recurring_start, recurring_end)
        for event in events_recurring:
            events_for_date = clean_event(
                event,
                calendar_type,
                start_datetime,
                end_datetime,
                target_date,
                events_for_date,
            )

    logger.info(f"Found {len(events_for_date)} events for {target_date}")
    return events_for_date


# -------------------------------------------------------------------
# 2. NOTE UPDATING
# -------------------------------------------------------------------


def remove_all_calendar_sections(content):
    """
    Removes all calendar sections from the content, regardless of slight
    header variations.
    Returns (cleaned_content, number_of_sections_removed)
    """
    lines = content.splitlines()
    new_lines = []
    in_calendar_section = False
    sections_removed = 0

    for line in lines:
        # Check for any variation of calendar headers
        if (
            line.strip().lower().startswith(("#", "##", "###"))
            and "calendar" in line.strip().lower()
        ):
            in_calendar_section = True
            sections_removed += 1
            continue

        if in_calendar_section:
            if line.strip().startswith(("#", "##", "###")):
                in_calendar_section = False
                new_lines.append(line)  # Keep that header
        else:
            new_lines.append(line)

    return "\n".join(new_lines), sections_removed


def format_events_as_markdown(events_with_types):
    """
    Takes a list of (event, calendar_type) tuples and returns a
    markdown string without appending any timezone abbreviations.
    """
    if not events_with_types:
        return "_No events today_\n"

    seen_events = set()
    lines = []
    tz = ZoneInfo("America/New_York")

    for evt, cal_type in events_with_types:
        event_id = (evt.get("summary", ""), evt.get("dtstart").dt, cal_type)
        if event_id in seen_events:
            continue
        seen_events.add(event_id)

        event_name = evt.get("summary", "Untitled Event")
        start_time = evt.get("dtstart").dt
        end_time = evt.get("dtend").dt if evt.get("dtend") else start_time

        # Check if this is an all-day event
        is_all_day = isinstance(start_time, datetime.date) and not isinstance(
            start_time, datetime.datetime
        )

        if not is_all_day:
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=tz)
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=tz)
            start_time_str = start_time.astimezone(tz).strftime("%H:%M")
            end_time_str = end_time.astimezone(tz).strftime("%H:%M")

        calendar_name = CALENDAR_LABELS.get(cal_type, "(Other 🤷)")

        # Pick an emoji based on event keywords
        event_emoji = "📅"
        event_lower = event_name.lower()
        for keyword, emoji in EVENT_KEYWORDS.items():
            if keyword in event_lower:
                event_emoji = emoji
                break

        # Construct the main event link (URL or fallback search link)
        if evt.get("url"):
            event_text = f"[{event_name}]({evt.get('url')})"
        else:
            search_query = event_name.replace(" ", "+")
            google_cal_link = (
                f"https://calendar.google.com/calendar/u/0/r/search?q={search_query}"
            )
            event_text = f"[{event_name}]({google_cal_link})"

        # Handle location
        event_details = []
        location_details = []
        location = evt.get("location", "").strip()
        if location:
            if any(
                domain in location.lower()
                for domain in [
                    "http://",
                    "https://",
                    "zoom.us",
                    "meet.google",
                    "teams.microsoft",
                ]
            ):
                event_details.append(f"🔗 [Join meeting]({location})")
            else:
                clean_location = " ".join(location.replace("\n", " ").split())
                maps_query = clean_location.replace(" ", "+")
                maps_link = (
                    f"https://www.google.com/maps/search/?api=1&query={maps_query}"
                )
                location_details.append(f"📍 [{clean_location}]({maps_link})")

        # Handle description for possible meeting links
        description = evt.get("description", "").strip()
        if description:
            urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', description)
            for url in urls:
                if any(
                    platform in url.lower()
                    for platform in [
                        "zoom.us",
                        "meet.google.com",
                        "teams.microsoft.com",
                    ]
                ):
                    if not any("Join meeting" in detail for detail in event_details):
                        event_details.append(f"🔗 [Join meeting]({url})")
                        break

        # Final line
        if is_all_day:
            line = f"- 📅 {event_text} {event_emoji} `{calendar_name}`\n"
        else:
            line = f"- **{start_time_str} - {end_time_str}** {event_text} `{calendar_name}`\n"

        # Indent additional details
        if event_details:
            line += "".join(f"    - {detail}\n" for detail in event_details)
        if location_details:
            line += "".join(f"    - {loc}\n" for loc in location_details)

        lines.append(line.rstrip())

    return "\n".join(lines) + "\n"


def insert_calendar_at_top(note_content, events_md):
    """
    Inserts the calendar events after a known table (if present)
    but before the rest of the note.
    """
    lines = note_content.splitlines()
    table_end_idx = -1

    for i, line in enumerate(lines):
        if "|" in line and "[[" in line and "]]" in line:
            table_end_idx = i

    if table_end_idx == -1:
        return HEADER_CALENDAR_EVENTS + "\n" + events_md + note_content

    before = lines[: table_end_idx + 1]
    after = lines[table_end_idx + 1 :]  # noqa: E203
    return (
        "\n".join(before)
        + "\n\n"
        + HEADER_CALENDAR_EVENTS
        + events_md
        + "\n"
        + "\n".join(after)
    )


def update_note(file_path, events):
    """
    Load the file, remove all calendar sections, then add the new one at
    the top.
    """
    logger.info(f"Updating note: {file_path}")
    if os.path.exists(file_path):
        logger.info("File exists, reading content...")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        logger.info("File doesn't exist, starting with blank content")
        content = ""

    content_no_old, sections_removed = remove_all_calendar_sections(content)
    if sections_removed > 0:
        logger.info(f"Removed {sections_removed} calendar section(s)")

    events_md = format_events_as_markdown(events)
    updated_content = insert_calendar_at_top(content_no_old, events_md)

    logger.info(f"Writing updated content with {len(events)} events")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated_content)


# -------------------------------------------------------------------
# 3. MAIN LOGIC
# -------------------------------------------------------------------


def extract_date_from_filename(filename):
    """
    Attempt to parse 'mm-dd-yyyy' from filenames like '12-21-2024 (Sat) 📝.md'
    Return a datetime.date object or None if not parseable.
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


def main():
    """
    - Find all markdown files in a specified directory (e.g. ./TODO/),
      excluding any path that contains '/Archive/' or '/Weekly/'.
    - For each file, parse the date from the filename.
    - Fetch ICS events for that date from multiple calendars.
    - Update the file with the new events at the top.
    """
    logger.info("Starting calendar update script...")

    # Define calendar URLs with their types (replace with your own environment variables or strings)
    calendar_configs = [
        (os.getenv("GOOGLE_CALENDAR_PERSONAL"), "personal"),
        (os.getenv("GOOGLE_CALENDAR_EVENTS"), "events"),
        (os.getenv("GOOGLE_CALENDAR_HOLIDAYS_US"), "us_holidays"),
    ]
    ics_urls_with_types = [(url, cal_type) for url, cal_type in calendar_configs if url]

    todo_dir = "TODO"
    logger.info(f"Scanning directory: {todo_dir}")

    files_processed = 0
    skip_dirs = ["Archive", "Weekly"]

    for root, dirs, files in os.walk(todo_dir):
        if any(skip_dir in root.split(os.sep) for skip_dir in skip_dirs):
            logger.info(f"Skipping directory: {root}")
            continue

        for filename in files:
            if not filename.lower().endswith(".md"):
                continue

            file_path = os.path.join(root, filename)
            file_date = extract_date_from_filename(filename)

            if not file_date:
                logger.info(f"Skipping file (no date found): {filename}")
                continue

            logger.info(f"Processing file: {filename}")
            events = fetch_events_for_date(ics_urls_with_types, file_date)
            update_note(file_path, events)
            files_processed += 1

    logger.info(f"Finished processing {files_processed} files")


if __name__ == "__main__":
    main()

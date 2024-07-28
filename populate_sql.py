import os
import datetime
import pickle
import sqlite3
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pytz
from googleapiclient.discovery import build

CLIENT_SECRETS_FILE = 'client_id.json'

SCOPES = ['https://www.googleapis.com/auth/calendary']
CENTRAL_TIMEZONE = pytz.timezone('America/Chicago')

def get_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    service = build('calendar', 'v3', credentials=creds)
    return service


def localize_time(time):
    if time.tzinfo is None:
        return CENTRAL_TIMEZONE.localize(time)
    return time

def create_event(service, title, description, start_time, end_time, timezone='America/Chicago', 
                 location=None, attendees=None, recurrence=None, color_id=None, 
                 reminders=None, visibility=None): 

    event = {
        'summary': title,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': timezone,
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': timezone,
        }
    }

    if location:
        event['location'] = location
    if attendees:
        event['attendees'] = attendees
    if recurrence:
        event['recurrence'] = recurrence
    if color_id:
        event['colorId'] = color_id
    if reminders:
        event['reminders'] = reminders
    if visibility:
        event['visibility'] = visibility

    try:
        created_event = service.events().insert(calendarId='primary', body=event).execute()
        return created_event.get('id')
    except googleapiclient.errors.HttpError as error:
        print('An error occurred: %s' % error)


def add_event(service, event_id, conn, c):
    """Fetches event details from Google Calendar and inserts it into the local SQLite database."""
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        attendees_json = json.dumps(event.get('attendees', []))
        notifications_json = json.dumps(event.get('reminders', {}).get('overrides', []))
        
        c.execute('''
        INSERT OR REPLACE INTO events (
            id, summary, description, location, start_time, end_time, time_zone,
            status, created, updated, organizer, attendees, hangout_link,
            recurring_event_id, recurrence, color_id, visibility, notifications
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event.get('id'), event.get('summary'), event.get('description'), event.get('location'),
            event['start'].get('dateTime'), event['end'].get('dateTime'), event['start'].get('timeZone'),
            event.get('status'), event.get('created'), event.get('updated'), event['organizer'].get('email'),
            attendees_json, event.get('hangoutLink'), event.get('recurringEventId'),
            ', '.join(event.get('recurrence', [])), event.get('colorId'), event.get('visibility'),
            notifications_json
        ))
        
        conn.commit()
        print(f"Event {event.get('id')} inserted into the database.")
    
    except googleapiclient.errors.HttpError as error:
        print(f"An error occurred inserting the event with the following id `{event.get('id')}` to the database: {error}")

 
def fetch_events(service,conn, c, end_date):
    """Fetches upcoming events from all calendars associated with the user's Google Calendar account and updates the SQLite3 database."""
    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    print('Getting the upcoming events from all calendars')

    # Add list of calendars
    calendars = []

    for calendar_id in calendars:
        print(f'Fetching events from calendar: {calendar_id}')
        
        events_result = service.events().list(calendarId=calendar_id, timeMin=now, timeMax=end_date,
                                              singleEvents=True, orderBy='startTime').execute()
        events = events_result.get('items', [])

        for event in events:
            event_id = event.get('id', 'N/A')
            summary = event.get('summary', 'N/A')
            description = event.get('description', 'N/A')
            location = event.get('location', 'N/A')
            start_time = event['start'].get('dateTime', 'N/A')
            end_time = event['end'].get('dateTime', 'N/A')
            time_zone = event['start'].get('timeZone', 'N/A')
            status = event.get('status', 'N/A')
            created = event.get('created', 'N/A')
            updated = event.get('updated', 'N/A')
            organizer = event['organizer'].get('email', 'N/A')
            attendees = [{'email': attendee['email']} for attendee in event.get('attendees', [])]
            hangout_link = event.get('hangoutLink', 'N/A')
            recurring_event_id = event.get('recurringEventId', 'N/A')
            recurrence = event.get('recurrence', 'N/A')
            color_id = event.get('colorId', 'N/A')
            visibility = event.get('visibility', 'N/A')
            notifications = event.get('reminders', {}).get('overrides', [])
            
            attendees_json = json.dumps(attendees)
            notifications_json = json.dumps(notifications)

            c.execute('''
            INSERT OR REPLACE INTO events (id, summary, description, location, start_time, end_time, time_zone, status, created,
            updated, organizer, attendees, hangout_link, recurring_event_id, recurrence, color_id, visibility, notifications)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (event_id, summary, description, location, start_time, end_time, time_zone, status, created, updated, organizer, 
                  attendees_json, hangout_link, recurring_event_id, recurrence, color_id, visibility, notifications_json))
    conn.commit()
    print('Events have been updated in the database.')

def update_metadata(conn, c, last_updated, last_month):
    """Update the metadata table with the last updated time and last month."""
    c.execute('SELECT COUNT(*) FROM metadata')
    count = c.fetchone()[0]

    if count == 0:
        c.execute('INSERT INTO metadata (last_updated, last_month) VALUES (?, ?)', (last_updated, last_month))
    else:
        c.execute('UPDATE metadata SET last_updated = ?, last_month = ? WHERE id = 1', (last_updated, last_month))
    
    conn.commit()

def main():
    service = get_service()
    
    year = int(input("Enter the year (YYYY): ").strip())
    month = int(input("Enter the month (MM): ").strip())
    start_of_month = localize_time(datetime.datetime(year, month, 1, 0, 0, 0))
    if month == 12:
        end_of_month = localize_time(datetime.datetime(year + 1, 1, 1, 0, 0, 0))
    else:
        end_of_month = localize_time(datetime.datetime(year, month + 1, 1, 0, 0, 0))
    start_of_month = start_of_month.isoformat()
    end_date = end_of_month.isoformat()

    db_path = 'events.db'
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    last_updated = datetime.datetime.now()


    fetch_events(service, conn, c, end_date)
    update_metadata(conn, c, last_updated, end_of_month)

    print("Events have been successfully fetched and saved.")

if __name__ == '__main__':
    main()

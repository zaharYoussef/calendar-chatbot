from openai import OpenAI
import os
import json
import sqlite3
import re
from datetime import datetime
from dotenv import load_dotenv
from populate_sql import create_event, add_event, get_service, localize_time
load_dotenv()

CLIENT = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
)

TABLE_DESCRIPTION = (
        "The 'events' table in the database has the following columns: "
        "id (TEXT, PRIMARY KEY) - Unique identifier for the event, "
        "summary (TEXT) - Title of the event, "
        "description (TEXT) - Description of the event, "
        "location (TEXT) - Location where the event takes place, "
        "start_time (TEXT) - Start time of the event, "
        "end_time (TEXT) - End time of the event, "
        "time_zone (TEXT) - Time zone of the event, "
        "status (TEXT) - Status of the event (e.g., confirmed, tentative), "
        "created (TEXT) - Creation timestamp of the event, "
        "updated (TEXT) - Last updated timestamp of the event, "
        "organizer (TEXT) - Email of the event organizer, "
        "attendees (TEXT) - List of attendees (emails), "
        "hangout_link (TEXT) - Link to the Google Hangout for the event, "
        "recurring_event_id (TEXT) - ID of the recurring event if this event is part of a series, "
        "recurrence (TEXT) - Recurrence rules for the event, "
        "color_id (TEXT) - Color ID of the event. Possible values are: "
        "1 (Lavender - #7986cb), 2 (Sage - #33b679), 3 (Grape - #8e24aa), 4 (Flamingo - #e67c73), "
        "5 (Banana - #f6c026), 6 (Tangerine - #f5511d), 7 (Peacock - #039be5), 8 (Graphite - #616161), "
        "9 (Blueberry - #3f51b5), 10 (Basil - #0b8043), 11 (Tomato - #d60000), "
        "visibility (TEXT) - Visibility of the event (e.g., default, public, private), "
        "notifications (TEXT) - Notifications for the event (reminders)."
    )

def load_metadata(c):
    """Load metadata from SQLite database."""
    c.execute('SELECT last_updated, last_month FROM metadata WHERE id = 1')
    metadata = c.fetchone()
        
    if metadata:
        return {
            "last_updated": metadata[0],
            "last_month": metadata[1]
        }
    else:
        return {
            "last_updated": "N/A",
            "last_month": "N/A"
        }

def get_prompt_intent(prompt, metadata, current_time):
    """ Get the intent from the user prompt to be used to extract the necessary info"""
    
    completion = CLIENT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant helping with extracting information from calendar events and answer questions regarding the events."
                    f"The current time and date is: {current_time}"
                    f"The last time the database was updated is: {metadata['last_updated']}. "
                    f"The events in the database are up to the day before: {metadata['last_month']}. "
                    f"{TABLE_DESCRIPTION}"
                    "If we are inserting an event extract all the info needed to fill the values in our table, return this as a yaml file and make sure the time is in the follwing format: YYYY-MM-DD HH:MM or YYYY-MM-DD if it's a whole day event "
                    " If we are searching generate SQL queries to retrieve the necessary information from the database or create an event. only return said query no extra text"
                )
            },
            {
                "role": "user", 
                "content": prompt
            }
        ]    
    )
    return completion.choices[0].message.content

def generate_descriptive_response(question, results):
    """Generate a descriptive response based on the initial question and query results."""
    
    completion = CLIENT.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an assistant helping with interpreting database query results and providing descriptive responses as part of a chatbot."
                    "Given a user's question and the results of a SQL query, formulate a helpful and informative response."
                    f"{TABLE_DESCRIPTION}"
                    "Time zone is America/Chicago"
                )
            },
            {
                "role": "user",
                "content": (
                    f"User's question: {question}\n"
                    f"SQL query results: {results}\n"
                    "Provide a descriptive and informative response based on the user's question and the query results, do not mention that you ar using a sql query in your reponse."
                )
            }
        ]
    )
    return completion.choices[0].message.content


def get_user_confirmation(prompt, default_value):
    """Prompt the user to confirm or modify a value."""
    user_input = input(f"{prompt} [{default_value}]: ")
    return user_input.strip() if user_input else default_value
    
def confirm_and_modify_event_details(event_data):
    """Confirm or modify event details."""
    print("Here are the event details:")
    for key, value in event_data.items():
        print(f"{key}: {value}")
    is_correct = input("Are these details correct? (yes/no): ").strip().lower()

    if is_correct != 'yes':
        title = get_user_confirmation("Summary", event_data.get('summary'))
        description = get_user_confirmation("Description", event_data.get('description'))
        start_time = get_user_confirmation("Start Time (YYYY-MM-DD HH:MM)", event_data.get('start_time'))
        end_time = get_user_confirmation("End Time (YYYY-MM-DD HH:MM)", event_data.get('end_time'))
        timezone = get_user_confirmation("Time Zone", event_data.get('time_zone', 'America/Chicago'))
        location = get_user_confirmation("Location", event_data.get('location'))
        attendees = get_user_confirmation("Attendees (comma separated emails)", event_data.get('attendees'))
        recurrence = get_user_confirmation("Recurrence", event_data.get('recurrence'))
        color_id = get_user_confirmation("Color ID", event_data.get('color_id'))
        reminders = get_user_confirmation("Notifications", event_data.get('notifications'))
        visibility = get_user_confirmation("Visibility", event_data.get('visibility'))
        organizer = event_data.get('organizer')

        start_time = localize_time(datetime.strptime(start_time, "%Y-%m-%d %H:%M"))
        end_time = localize_time(datetime.strptime(end_time, "%Y-%m-%d %H:%M"))

        attendees = [{'email': email.strip()} for email in attendees.split(',') if email.strip()]
    else:
        title = event_data.get('summary')
        description = event_data.get('description')
        start_time = localize_time(datetime.strptime(event_data.get('start_time'), "%Y-%m-%d %H:%M"))
        end_time = localize_time(datetime.strptime(event_data.get('end_time'), "%Y-%m-%d %H:%M"))
        timezone = event_data.get('time_zone', 'America/Chicago')
        location = event_data.get('location')
        attendees = [{'email': email.strip()} for email in event_data.get('attendees', '').split(',') if email.strip()]
        recurrence = event_data.get('recurrence')
        color_id = event_data.get('color_id')
        reminders = event_data.get('notifications')
        visibility = event_data.get('visibility')
        organizer = event_data.get('organizer')

    return {
        'summary': title,
        'description': description,
        'start_time': start_time,
        'end_time': end_time,
        'timezone': timezone,
        'location': location,
        'attendees': attendees,
        'recurrence': recurrence,
        'color_id': color_id,
        'reminders': reminders,
        'visibility': visibility,
        'organizer': organizer
    }

def extract_sql_query(response):
    """Extract SQL query from the bot's response using regex."""
    match = re.search(r'```sql(.*?)```', response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None
 
def parse_key_value_response(response):
    """Parse a key-value formatted response into a dictionary."""
    event_data = {}
    for line in response.split('\n'):
        if ': ' in line:
            key, value = line.split(': ', 1)
            event_data[key.strip()] = value.strip().strip('"')
    return event_data

def main():
    print("Welcome to the CLI Chatbot! Type 'exit' to end the conversation.")
    conn = sqlite3.connect('events.db')
    c = conn.cursor()
    metadata = load_metadata(c)
    current_time = datetime.now()
    service = get_service()
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            print("Goodbye!")
            break
        bot_response = get_prompt_intent(user_input, metadata, current_time)
        sql_query = extract_sql_query(bot_response)

        if sql_query:
            c.execute(sql_query)
            results = c.fetchall()
            print(results)
            
            descriptive_response = generate_descriptive_response(user_input, results)
            print("Bot:", descriptive_response)
        else:
            if bot_response.strip().startswith("```yaml"):
                try:
                    event_data = parse_key_value_response(bot_response)
                    print('event was loaded')
                
                    event_details = confirm_and_modify_event_details(event_data)
                
                    event_id = create_event(
                        service,
                        event_details['summary'],
                        event_details['description'],
                        event_details['start_time'],
                        event_details['end_time'],
                        event_details['timezone'],
                        event_details['location'],
                        event_details['attendees'],
                        event_details['recurrence'],
                        event_details['color_id'],
                        event_details['reminders'],
                        event_details['visibility']
                    )
                
                    if event_id:
                        add_event(service, event_id, conn, c)
                        print(f"Event created and added to the database with ID: {event_id}")
                except ValueError as e:
                    print("ValueError parsing this info: ", bot_response)
                    print("The error is: ", e)
                except Exception as e:
                    print("An error has occurred: ", e)
            else:    
                print("Bot:", bot_response)
    
    conn.close()

if __name__ == '__main__':
    main()

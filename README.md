# Calendar Chatbot

This project is a chatbot designed to interact with Google Calendar, helping users manage busy schedules. Instead of manually searching through the calendar, users can ask the bot to create events or get event details. The bot uses OpenAI's gpt-4o-mini for communication and Retrieval-Augmented Generation (RAG) to provide accurate answers.

## Requirements

- Python 3.11.0
- SQLite3
- GPT-4o-mini (chosen for cost-efficiency and performance over GPT-3)

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Setup
1. Create a GCP Project:

2. Enable Google Calendar API

3. Setup Credentials:
   - Access User Data by setting up OAuth credentials.
   - Create a Desktop OAuth 2.0 Client ID and download the `client_ID.json` file and save it as `client_id.json`.

4. Obtain an OpenAI API key and add it to the .env file.

5. Install dotenv:
    ``` bash
    pip install python-dotenv
    ```

6. Create SQLite3 Database:

    ```bash
    sqlite3 events.db
    ```

7. Create events and metadata tables
   1. Create Events Table:

        ``` sql
        CREATE TABLE events(
            id TEXT PRIMARY KEY,
            summary TEXT,
            description TEXT,
            location TEXT,
            start_time TEXT,
            end_time TEXT,
            time_zone TEXT,
            status TEXT,
            created TEXT,
            updated TEXT,
            organizer TEXT,
            attendees TEXT,
            hangout_link TEXT,
            recurring_event_id TEXT,
            recurrence TEXT,
            color_id TEXT,
            visibility TEXT,
            notifications TEXT
        );
        ```
    2. Create Metadata Table:

        ```sql
        CREATE TABLE metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_updated TEXT,
            last_month TEXT
        );
        ```


## Usage
1. Populate the Database:

    Add the list of calendars id you would like to be used while fetching events in the *fetch_events* function in `populate_sql.py`. If you are not sure what to use, run the following code to get a list of calendar id:
    ```python
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        for calendar in calendars:
            print(calendar['id'])
    ```
    
    Run the populate_sql.py file ```python populate_sql.py```. It will ask for a target date and will populate the database with events from the current date to the given date.
    
    
2. Run the Chatbot:
    ``` python chat_bot.py```


### Notes
This project is a work in progress and has not been fully tested, so it might break with some inputs. While the answers are not guaranteed to be 100% correct, the results have been accurate so far.

Future improvements planned for this project include:

- Adding the ability to edit and delete events.
- Implementing features for the creation, editing, and deletion of tasks.
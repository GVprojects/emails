import os
import csv
import re
import ssl
import smtplib
import threading
import time

from flask import (
    Flask,
    render_template,
    jsonify,
    request
)

from werkzeug.utils import secure_filename

from dotenv import load_dotenv

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


# ============================================================
# LOAD .ENV
# ============================================================

load_dotenv()


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

SENDER_EMAIL = os.getenv(
    "GV_SENDER_EMAIL",
    ""
).strip()


GMAIL_APP_PASSWORD = os.getenv(
    "GV_GMAIL_APP_PASSWORD",
    ""
).strip()


CONTACT_PHONE = "9885347542"

CONTACT_EMAIL = "gvprojects8@gmail.com"

WEBSITE_URL = "https://gvprojects.online"


EMAIL_SUBJECT = (
    "GV Projects - Final Year Projects & Research Papers"
)


EMAIL_DELAY = int(
    os.getenv(
        "EMAIL_DELAY",
        "5"
    )
)


# ============================================================
# FILE CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)


STATIC_DIR = os.path.join(
    BASE_DIR,
    "static"
)


UPLOAD_DIR = os.path.join(
    BASE_DIR,
    "uploads"
)


LOGO_FILE = os.path.join(
    STATIC_DIR,
    "logo.png"
)


os.makedirs(
    STATIC_DIR,
    exist_ok=True
)


os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


ALLOWED_EXTENSIONS = {
    "csv",
    "txt"
}


# ============================================================
# MAXIMUM UPLOAD SIZE
# ============================================================

# 10 MB

app.config[
    "MAX_CONTENT_LENGTH"
] = 10 * 1024 * 1024


# ============================================================
# EMAIL REGEX
# ============================================================

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+\."
    r"[A-Za-z]{2,}\b"
)


# ============================================================
# CAMPAIGN STATE
# ============================================================

state = {

    "emails": [],

    "students": [],

    "total": 0,

    "sent": 0,

    "failed": 0,

    "remaining": 0,

    "current": None,

    "status": "Idle",

    "sending": False,

    "stop_requested": False

}


# ============================================================
# HELPER
# ============================================================

def is_valid_email(email):

    if not email:
        return False

    return bool(
        EMAIL_REGEX.fullmatch(
            email.strip()
        )
    )


# ============================================================
# EXTRACT EMAILS FROM TEXT
# ============================================================

def extract_emails_from_text(text):

    found = EMAIL_REGEX.findall(
        text
    )

    result = []

    seen = set()


    for email in found:

        email = email.strip().lower()


        if email in seen:
            continue


        seen.add(email)

        result.append(email)


    return result


# ============================================================
# READ TXT
# ============================================================

def read_txt_file(filepath):

    emails = []

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        errors="ignore"
    ) as file:

        content = file.read()


    emails = extract_emails_from_text(
        content
    )


    return [
        {
            "name": "",
            "email": email
        }

        for email in emails
    ]


# ============================================================
# READ CSV
# ============================================================

def read_csv_file(filepath):

    students = []

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        errors="ignore",
        newline=""
    ) as file:

        reader = csv.DictReader(
            file
        )


        # ----------------------------------------------------
        # If CSV has headers
        # ----------------------------------------------------

        if reader.fieldnames:

            headers = {}

            for header in reader.fieldnames:

                if header:

                    headers[
                        header.strip().lower()
                    ] = header


            email_column = None
            name_column = None


            # Find email column

            for key in [
                "email",
                "email address",
                "gmail",
                "gmail address",
                "mail",
                "e-mail"
            ]:

                if key in headers:

                    email_column = headers[key]

                    break


            # Find name column

            for key in [
                "name",
                "student name",
                "student",
                "full name"
            ]:

                if key in headers:

                    name_column = headers[key]

                    break


            # ------------------------------------------------
            # CSV has email column
            # ------------------------------------------------

            if email_column:

                for row in reader:

                    email = (
                        row.get(
                            email_column,
                            ""
                        )
                        or ""
                    ).strip()


                    name = ""


                    if name_column:

                        name = (
                            row.get(
                                name_column,
                                ""
                            )
                            or ""
                        ).strip()


                    if is_valid_email(
                        email
                    ):

                        students.append({

                            "name": name,

                            "email":
                                email.lower()

                        })


                return remove_duplicate_students(
                    students
                )


    # ========================================================
    # FALLBACK
    # ========================================================

    # If the CSV doesn't have a recognized email header,
    # read the entire file as text and extract email addresses.

    with open(
        filepath,
        "r",
        encoding="utf-8-sig",
        errors="ignore"
    ) as file:

        content = file.read()


    emails = extract_emails_from_text(
        content
    )


    return [

        {
            "name": "",
            "email": email
        }

        for email in emails

    ]


# ============================================================
# REMOVE DUPLICATES
# ============================================================

def remove_duplicate_students(
    students
):

    result = []

    seen = set()


    for student in students:

        email = student[
            "email"
        ].strip().lower()


        if not is_valid_email(
            email
        ):

            continue


        if email in seen:

            continue


        seen.add(email)


        result.append({

            "name":
                student.get(
                    "name",
                    ""
                ),

            "email":
                email

        })


    return result


# ============================================================
# LOAD FILE
# ============================================================

def process_uploaded_file(
    filepath
):

    extension = (
        os.path.splitext(
            filepath
        )[1]
        .lower()
        .replace(
            ".",
            ""
        )
    )


    if extension == "csv":

        return read_csv_file(
            filepath
        )


    if extension == "txt":

        return read_txt_file(
            filepath
        )


    raise ValueError(
        "Only CSV and TXT files are supported."
    )


# ============================================================
# APPLY STUDENTS
# ============================================================

def set_students(
    students
):

    students = remove_duplicate_students(
        students
    )


    state["students"] = students


    state["emails"] = [

        student["email"]

        for student in students

    ]


    state["total"] = len(
        students
    )


    state["sent"] = 0

    state["failed"] = 0

    state["remaining"] = state["total"]

    state["current"] = None

    state["status"] = "Emails Loaded"

    state["sending"] = False

    state["stop_requested"] = False


# ============================================================
# UPLOAD CSV / TXT
# ============================================================

@app.route(
    "/api/upload",
    methods=["POST"]
)
def upload_file():

    if "file" not in request.files:

        return jsonify({

            "success": False,

            "message":
                "Please select a CSV or TXT file."

        })


    file = request.files[
        "file"
    ]


    if not file.filename:

        return jsonify({

            "success": False,

            "message":
                "No file selected."

        })


    filename = secure_filename(
        file.filename
    )


    extension = (
        os.path.splitext(
            filename
        )[1]
        .lower()
    )


    if extension not in [
        ".csv",
        ".txt"
    ]:

        return jsonify({

            "success": False,

            "message":
                "Only CSV and TXT files are allowed."

        })


    save_path = os.path.join(
        UPLOAD_DIR,
        filename
    )


    try:

        file.save(
            save_path
        )


        students = process_uploaded_file(
            save_path
        )


        if not students:

            return jsonify({

                "success": False,

                "message":
                    "No valid email addresses were found in the file."

            })


        set_students(
            students
        )


        return jsonify({

            "success": True,

            "message":
                "File uploaded successfully.",

            "filename":
                filename,

            "count":
                state["total"],

            "emails":
                state["emails"],

            "students":
                state["students"]

        })


    except Exception as error:

        print(
            "Upload error:",
            error
        )


        return jsonify({

            "success": False,

            "message":
                f"Could not process file: {error}"

        })


# ============================================================
# LOAD CURRENT UPLOADED EMAILS
# ============================================================

@app.route(
    "/api/load-emails",
    methods=["POST"]
)
def load_emails():

    # This endpoint is retained so your existing
    # index.html LOAD EMAILS button continues working.

    if state["emails"]:

        return jsonify({

            "success": True,

            "count":
                state["total"],

            "emails":
                state["emails"],

            "students":
                state["students"]

        })


    # Look for the most recently modified CSV/TXT file.

    files = []


    for filename in os.listdir(
        UPLOAD_DIR
    ):

        path = os.path.join(
            UPLOAD_DIR,
            filename
        )


        if (
            os.path.isfile(path)
            and
            filename.lower().endswith(
                (
                    ".csv",
                    ".txt"
                )
            )
        ):

            files.append(
                path
            )


    if not files:

        return jsonify({

            "success": False,

            "message":
                "Please upload a CSV or TXT file first."

        })


    latest_file = max(
        files,
        key=os.path.getmtime
    )


    try:

        students = process_uploaded_file(
            latest_file
        )


        set_students(
            students
        )


        return jsonify({

            "success": True,

            "count":
                state["total"],

            "emails":
                state["emails"],

            "students":
                state["students"]

        })


    except Exception as error:

        return jsonify({

            "success": False,

            "message":
                str(error)

        })


# ============================================================
# EMAIL HTML
# ============================================================

def create_email_html(
    student_name=""
):

    if not student_name:

        student_name = "Student"


    return f"""
<!DOCTYPE html>

<html>

<head>

<meta charset="UTF-8">

<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>GV Projects</title>

</head>


<body style="
margin:0;
padding:0;
background:#05070b;
font-family:Arial,Helvetica,sans-serif;
">


<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="
background:#05070b;
padding:30px 10px;
">

<tr>

<td align="center">


<table
width="600"
cellpadding="0"
cellspacing="0"
border="0"
style="
width:100%;
max-width:600px;
background:#ffffff;
border-radius:16px;
overflow:hidden;
">


<!-- HEADER -->

<tr>

<td
align="center"
style="
background:#050a12;
padding:30px 20px 25px;
border-bottom:4px solid #ff5a00;
">


<img
src="cid:gvprojectslogo"
alt="GV Projects Logo"
width="150"
style="
width:150px;
max-width:45%;
height:auto;
display:block;
margin:0 auto 15px;
">


<div style="
font-size:25px;
font-weight:bold;
color:#ffffff;
letter-spacing:1px;
">

GV
<span style="
color:#ff5a00;
">
PROJECTS
</span>

</div>


<div style="
margin-top:7px;
color:#5fc7ff;
font-size:10px;
letter-spacing:2px;
">

PROJECTS • RESEARCH • DEVELOPMENT

</div>


</td>

</tr>


<!-- BODY -->

<tr>

<td
style="
padding:30px 28px;
color:#252b35;
font-size:14px;
line-height:1.7;
">


<p style="margin-top:0;">

Hi {student_name},

</p>


<p>

We provide
<strong>
final-year projects,
research papers,
and project development support
</strong>
at affordable prices.

</p>


<p>

Looking for a project or research paper?

Explore our available projects
and choose one according to your
requirements.

</p>


<!-- SERVICES -->

<table
width="100%"
cellpadding="0"
cellspacing="8"
border="0"
>

<tr>


<td
align="center"
style="
background:#f3f7fb;
padding:16px 5px;
border-radius:8px;
">

<div style="font-size:22px;">
💻
</div>

<strong style="
font-size:11px;
color:#172033;
">

Final-Year Projects

</strong>

</td>


<td
align="center"
style="
background:#f3f7fb;
padding:16px 5px;
border-radius:8px;
">

<div style="font-size:22px;">
📄
</div>

<strong style="
font-size:11px;
color:#172033;
">

Research Papers

</strong>

</td>


<td
align="center"
style="
background:#f3f7fb;
padding:16px 5px;
border-radius:8px;
">

<div style="font-size:22px;">
🛠️
</div>

<strong style="
font-size:11px;
color:#172033;
">

Project Support

</strong>

</td>


</tr>

</table>


<!-- CONTACT -->

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="margin-top:22px;"
>

<tr>

<td
style="
background:#fff5ef;
border-left:4px solid #ff5a00;
padding:16px;
border-radius:7px;
">


<strong>
Contact GV Projects
</strong>

<br><br>


📞
<a
href="tel:{CONTACT_PHONE}"
style="
color:#222;
text-decoration:none;
"
>
{CONTACT_PHONE}
</a>

<br>


📧
<a
href="mailto:{CONTACT_EMAIL}"
style="
color:#222;
text-decoration:none;
"
>
{CONTACT_EMAIL}
</a>


</td>

</tr>

</table>


<!-- BUTTON -->

<table
width="100%"
cellpadding="0"
cellspacing="0"
border="0"
style="margin-top:25px;"
>

<tr>

<td align="center">


<a
href="{WEBSITE_URL}"
target="_blank"
style="
display:inline-block;
padding:14px 28px;
background:#087fe5;
color:#ffffff;
text-decoration:none;
border-radius:8px;
font-size:13px;
font-weight:bold;
letter-spacing:.5px;
">

BROWSE GV PROJECTS

</a>


</td>

</tr>

</table>


<p
style="
margin-top:28px;
margin-bottom:0;
"
>

Regards,<br>

<strong>
GV Projects Team
</strong>

</p>


</td>

</tr>


<!-- FOOTER -->

<tr>

<td
align="center"
style="
background:#07101b;
padding:20px;
color:#8493a6;
font-size:10px;
">


<strong style="
color:#ff5a00;
">

GV PROJECTS

</strong>


<br><br>


Final-Year Projects • Research Papers • Project Support


<br><br>


<a
href="{WEBSITE_URL}"
style="
color:#53c5ff;
text-decoration:none;
">

gvprojects.online

</a>


</td>

</tr>


</table>

</td>

</tr>

</table>


</body>

</html>
"""


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(
    recipient,
    student_name=""
):

    if not SENDER_EMAIL:

        raise Exception(
            "GV_SENDER_EMAIL is missing from .env"
        )


    if not GMAIL_APP_PASSWORD:

        raise Exception(
            "GV_GMAIL_APP_PASSWORD is missing from .env"
        )


    if not os.path.exists(
        LOGO_FILE
    ):

        raise Exception(
            "Logo not found: "
            + LOGO_FILE
        )


    # --------------------------------------------------------
    # ROOT MESSAGE
    # --------------------------------------------------------

    message = MIMEMultipart(
        "related"
    )


    message["From"] = SENDER_EMAIL

    message["To"] = recipient

    message["Subject"] = EMAIL_SUBJECT


    # --------------------------------------------------------
    # ALTERNATIVE
    # --------------------------------------------------------

    alternative = MIMEMultipart(
        "alternative"
    )


    # Plain text version

    plain_text = f"""
Hi {student_name or "Student"},

We provide final-year projects, research papers,
and project development support at affordable prices.

Browse our projects:

{WEBSITE_URL}

Contact:

{CONTACT_PHONE}
{CONTACT_EMAIL}

Regards,
GV Projects Team
"""


    alternative.attach(
        MIMEText(
            plain_text,
            "plain",
            "utf-8"
        )
    )


    # HTML version

    html = create_email_html(
        student_name
    )


    alternative.attach(
        MIMEText(
            html,
            "html",
            "utf-8"
        )
    )


    message.attach(
        alternative
    )


    # --------------------------------------------------------
    # EMBED LOGO
    # --------------------------------------------------------

    with open(
        LOGO_FILE,
        "rb"
    ) as image_file:

        logo = MIMEImage(
            image_file.read()
        )


    logo.add_header(
        "Content-ID",
        "<gvprojectslogo>"
    )


    logo.add_header(
        "Content-Disposition",
        "inline",
        filename="gvprojects-logo.png"
    )


    message.attach(
        logo
    )


    # --------------------------------------------------------
    # SMTP
    # --------------------------------------------------------

    context = ssl.create_default_context()


    with smtplib.SMTP(
        "smtp.gmail.com",
        587
    ) as server:

        server.starttls(
            context=context
        )


        server.login(
            SENDER_EMAIL,
            GMAIL_APP_PASSWORD
        )


        server.sendmail(
            SENDER_EMAIL,
            recipient,
            message.as_string()
        )


# ============================================================
# CAMPAIGN WORKER
# ============================================================

def campaign_worker():

    state["sending"] = True

    state["stop_requested"] = False

    state["status"] = "Sending"


    for student in state["students"]:

        if state[
            "stop_requested"
        ]:

            state[
                "status"
            ] = "Stopped"

            break


        recipient = student[
            "email"
        ]


        name = student.get(
            "name",
            ""
        )


        state[
            "current"
        ] = recipient


        try:

            send_email(
                recipient,
                name
            )


            state[
                "sent"
            ] += 1


        except Exception as error:

            state[
                "failed"
            ] += 1


            print(
                "Failed:",
                recipient,
                error
            )


        state[
            "remaining"
        ] = max(
            state["total"]
            -
            state["sent"]
            -
            state["failed"],
            0
        )


        if not state[
            "stop_requested"
        ]:

            time.sleep(
                EMAIL_DELAY
            )


    state[
        "sending"
    ] = False


    state[
        "current"
    ] = None


    if (
        state["sent"]
        +
        state["failed"]
        >=
        state["total"]
    ):

        state[
            "status"
        ] = "Completed"


# ============================================================
# START CAMPAIGN
# ============================================================

@app.route(
    "/api/start",
    methods=["POST"]
)
def start_campaign():

    if state["sending"]:

        return jsonify({

            "success": False,

            "message":
                "Campaign is already running."

        })


    if not state["students"]:

        return jsonify({

            "success": False,

            "message":
                "Please upload a CSV or TXT file first."

        })


    if not SENDER_EMAIL:

        return jsonify({

            "success": False,

            "message":
                "Sender Gmail is missing in .env."

        })


    if not GMAIL_APP_PASSWORD:

        return jsonify({

            "success": False,

            "message":
                "Gmail App Password is missing in .env."

        })


    state["sent"] = 0

    state["failed"] = 0

    state["remaining"] = state["total"]

    state["current"] = None

    state["status"] = "Starting"


    thread = threading.Thread(
        target=campaign_worker,
        daemon=True
    )


    thread.start()


    return jsonify({

        "success": True,

        "message":
            f"Campaign started for "
            f"{state['total']} recipients."

    })


# ============================================================
# STOP CAMPAIGN
# ============================================================

@app.route(
    "/api/stop",
    methods=["POST"]
)
def stop_campaign():

    state[
        "stop_requested"
    ] = True


    state[
        "status"
    ] = "Stopping"


    return jsonify({

        "success": True,

        "message":
            "Campaign stop requested."

    })


# ============================================================
# TEST EMAIL
# ============================================================

@app.route(
    "/api/test",
    methods=["POST"]
)
def test_email():

    data = request.get_json(
        silent=True
    ) or {}


    recipient = (
        data.get(
            "test_recipient",
            ""
        )
        .strip()
    )


    if not recipient:

        return jsonify({

            "success": False,

            "message":
                "Enter a test email address."

        })


    if not is_valid_email(
        recipient
    ):

        return jsonify({

            "success": False,

            "message":
                "Invalid email address."

        })


    try:

        send_email(
            recipient,
            "Student"
        )


        return jsonify({

            "success": True,

            "message":
                "Test email sent successfully."

        })


    except Exception as error:

        print(
            "Test email error:",
            error
        )


        return jsonify({

            "success": False,

            "message":
                str(error)

        })


# ============================================================
# STATUS
# ============================================================

@app.route(
    "/api/status"
)
def status():

    return jsonify({

        "total":
            state["total"],

        "sent":
            state["sent"],

        "failed":
            state["failed"],

        "remaining":
            state["remaining"],

        "current":
            state["current"],

        "status":
            state["status"],

        "sending":
            state["sending"]

    })


# ============================================================
# EMAIL PREVIEW
# ============================================================

@app.route(
    "/api/email-preview"
)
def email_preview():

    return create_email_html(
        "Student"
    )


# ============================================================
# CURRENT EMAILS
# ============================================================

@app.route(
    "/api/emails"
)
def get_emails():

    return jsonify({

        "success": True,

        "count":
            state["total"],

        "students":
            state["students"],

        "emails":
            state["emails"]

    })


# ============================================================
# HOME
# ============================================================

@app.route("/")
def index():

    return render_template(
        "index.html",
        email_count=
            state["total"]
    )


# ============================================================
# UPLOAD ERROR
# ============================================================

@app.errorhandler(
    413
)
def too_large(error):

    return jsonify({

        "success": False,

        "message":
            "File is too large. Maximum size is 10 MB."

    }), 413


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print()
    print(
        "=========================================="
    )
    print(
        "        GV PROJECTS EMAIL SYSTEM"
    )
    print(
        "=========================================="
    )

    print(
        "Sender:",
        SENDER_EMAIL or "NOT CONFIGURED"
    )

    print(
        "Website:",
        WEBSITE_URL
    )

    print(
        "Logo:",
        LOGO_FILE
    )

    print(
        "Email delay:",
        EMAIL_DELAY,
        "seconds"
    )

    print(
        "=========================================="
    )
    print()


    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
# Lost and Found System

A Flask application for reporting and managing lost items, with a MySQL database.

## Requirements

- Python 3
- MySQL
- Dependencies from `requirements.txt`

## Configuration

Set these environment variables before starting the application:

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `FLASK_SECRET_KEY` | Yes | — | A long, random secret used to sign sessions. |
| `DB_HOST` | No | `localhost` | MySQL server host. |
| `DB_PORT` | No | `3306` | MySQL server port. |
| `DB_USER` | No | `root` | MySQL username. |
| `DB_PASSWORD` | No | Empty | MySQL password. |
| `DB_NAME` | No | `finder_db` | Database name. |
| `ADMIN_USERNAME` | No | — | Username for creating the initial admin account. |
| `ADMIN_PASSWORD` | No | — | Password for creating the initial admin account. |
| `FLASK_DEBUG` | No | `false` | Set to `true` only for local development. |

The database must exist before starting the app. If both admin variables are
set, the application creates that admin account if it does not already exist.
If neither is set, no initial admin account is created. Do not commit real
secrets or passwords to the repository.

## Run locally

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Set environment variables in PowerShell, then run:

```powershell
$env:FLASK_SECRET_KEY = "<a long random value>"
$env:DB_PASSWORD = "<your MySQL password>"
python app.py
```

To create an initial admin, also set `ADMIN_USERNAME` and `ADMIN_PASSWORD`
before the first run.

## Deploy on Railway

1. Create a Railway project and deploy this GitHub repository as a service.
2. Add a MySQL service to the same Railway project.
3. In the web service's Variables, add `FLASK_SECRET_KEY` with a long,
   randomly generated value. Set `ADMIN_USERNAME` and `ADMIN_PASSWORD` to
   create the first administrator account.
4. Add references in the web service to the MySQL service's `MYSQLHOST`,
   `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE` variables.
   The application reads these variables directly.
5. Set the web service's Start Command to:

   ```sh
   gunicorn --bind 0.0.0.0:$PORT wsgi:app
   ```

   `wsgi.py` creates the database tables when the service starts.
6. Deploy, then use the web service's Settings to generate a public domain.

Keep all passwords and secret keys in Railway's Variables, not in GitHub.

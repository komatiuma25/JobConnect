import os
from flask import send_from_directory

import oracledb
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash, session
)
from werkzeug.security import check_password_hash
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename
from database import get_connection
from flask import render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
ALLOWED_EXTENSIONS = {"pdf"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "development-key-change-before-deployment"
)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        if not full_name or not email or not password:
            flash("Please complete all required fields.", "error")
            return render_template("register.html")

        if role not in ("job_seeker", "employer"):
            flash("Please select a valid account type.", "error")
            return render_template("register.html")

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)
        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO users
                    (full_name, email, password_hash, role)
                VALUES
                    (:full_name, :email, :password_hash, :role)
                """,
                {
                    "full_name": full_name,
                    "email": email,
                    "password_hash": password_hash,
                    "role": role,
                },
            )

            connection.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("login"))

        except oracledb.IntegrityError:
            if connection:
                connection.rollback()
            flash("This email may already be registered.", "error")

        except oracledb.Error:
            if connection:
                connection.rollback()
            app.logger.exception("Database error during registration")
            flash("Unable to complete registration. Please try again.", "error")

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter your email and password.", "error")
            return render_template("login.html")

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT user_id, full_name, email,
                       password_hash, role
                FROM users
                WHERE email = :email
                """,
                {"email": email}
            )

            user = cursor.fetchone()

            if user and check_password_hash(user[3], password):
                session.clear()
                session["user_id"] = user[0]
                session["full_name"] = user[1]
                session["email"] = user[2]
                session["role"] = user[4]

                flash(
                    f"Welcome back, {user[1]}!",
                    "success"
                )
                return redirect(url_for("home"))

            flash("Invalid email or password.", "error")

        except oracledb.Error:
            app.logger.exception("Database error during login")
            flash("Unable to log in right now. Please try again.", "error")

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("home"))

@app.route("/jobs")
def jobs():
    title = request.args.get("title", "").strip()
    location = request.args.get("location", "").strip()
    company = request.args.get("company", "").strip()
    min_salary_input = request.args.get("min_salary", "").strip()

    # Validate minimum salary
    min_salary = None

    if min_salary_input:
        try:
            min_salary = float(min_salary_input)

            if min_salary < 0:
                flash("Minimum salary cannot be negative.", "error")
                return render_template("jobs.html", jobs=[])

        except ValueError:
            flash("Please enter a valid minimum salary.", "error")
            return render_template("jobs.html", jobs=[])

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        query = """
            SELECT job_id, title, company_name, location,
                   required_skills, salary, posted_at
            FROM jobs
            WHERE (:title = '' OR LOWER(title) LIKE '%' || LOWER(:title) || '%')
              AND (:location = '' OR LOWER(NVL(location, '')) LIKE '%' || LOWER(:location) || '%')
              AND (:company = '' OR LOWER(NVL(company_name, '')) LIKE '%' || LOWER(:company) || '%')
              AND (:min_salary IS NULL OR salary >= :min_salary)
            ORDER BY posted_at DESC
        """

        cursor.execute(
            query,
            {
                "title": title,
                "location": location,
                "company": company,
                "min_salary": min_salary
            }
        )

        job_rows = cursor.fetchall()

        return render_template("jobs.html", jobs=job_rows)

    except oracledb.Error:
        app.logger.exception("Database error while loading jobs")
        flash("Unable to load jobs right now.", "error")
        return render_template("jobs.html", jobs=[])

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()



@app.route("/jobs/<int:job_id>")
def job_details(job_id):
    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT job_id, title, company_name, location,
                   description, required_skills, salary, posted_at
            FROM jobs
            WHERE job_id = :job_id
            """,
            {"job_id": job_id}
        )

        job = cursor.fetchone()

        if job is None:
            flash("Job not found.", "error")
            return redirect(url_for("jobs"))

        return render_template("job_details.html", job=job)

    except oracledb.Error:
        app.logger.exception("Database error while loading job details")
        flash("Unable to load this job right now.", "error")
        return redirect(url_for("jobs"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

@app.route("/employer/dashboard", methods=["GET", "POST"])
def employer_dashboard():
    if not session.get("user_id"):
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "employer":
        flash("Only employers can access this dashboard.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Handle job posting
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            company_name = request.form.get("company_name", "").strip()
            location = request.form.get("location", "").strip()
            description = request.form.get("description", "").strip()
            required_skills = request.form.get(
                "required_skills", ""
            ).strip()
            salary_input = request.form.get("salary", "").strip()

            salary = None

            if salary_input:
                try:
                    salary = float(salary_input)
                    if salary < 0:
                        raise ValueError
                except ValueError:
                    flash("Please enter a valid, non-negative salary.", "error")
                    return redirect(url_for("employer_dashboard"))

            if not title or not company_name or not description:
                flash(
                    "Job title, company name, and description are required.",
                    "error"
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO jobs (
                        employer_id, title, company_name, location,
                        description, required_skills, salary
                    )
                    VALUES (
                        :employer_id, :title, :company_name, :location,
                        :description, :required_skills, :salary
                    )
                    """,
                    {
                        "employer_id": session["user_id"],
                        "title": title,
                        "company_name": company_name,
                        "location": location or None,
                        "description": description,
                        "required_skills": required_skills or None,
                        "salary": salary,
                    }
                )

                connection.commit()
                flash("Job posted successfully!", "success")
                return redirect(url_for("employer_dashboard"))

        employer_id = session["user_id"]

        # 1. Total jobs posted by this employer
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM jobs
            WHERE employer_id = :employer_id
            """,
            {"employer_id": employer_id}
        )
        total_jobs = cursor.fetchone()[0]

        # 2. Total applications received for this employer's jobs
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE j.employer_id = :employer_id
            """,
            {"employer_id": employer_id}
        )
        total_applications = cursor.fetchone()[0]

        # 3. Applications awaiting review
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE j.employer_id = :employer_id
              AND a.application_status = 'Pending'
            """,
            {"employer_id": employer_id}
        )
        pending_applications = cursor.fetchone()[0]

        # 4. Shortlisted candidates
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE j.employer_id = :employer_id
              AND a.application_status = 'Shortlisted'
            """,
            {"employer_id": employer_id}
        )
        shortlisted_candidates = cursor.fetchone()[0]

        # Get this employer's posted jobs
        cursor.execute(
            """
            SELECT job_id, title, company_name, location, posted_at
            FROM jobs
            WHERE employer_id = :employer_id
            ORDER BY posted_at DESC
            """,
            {"employer_id": employer_id}
        )

        employer_jobs = cursor.fetchall()

        return render_template(
            "employer_dashboard.html",
            jobs=employer_jobs,
            total_jobs=total_jobs,
            total_applications=total_applications,
            pending_applications=pending_applications,
            shortlisted_candidates=shortlisted_candidates
        )

    except oracledb.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Error loading employer dashboard")
        flash(
            "Unable to complete the operation. Please try again.",
            "error"
        )
        return redirect(url_for("home"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

@app.route("/apply/<int:job_id>", methods=["POST"])
def apply_job(job_id):
    if not session.get("user_id"):
        flash("Please log in to apply for a job.")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can apply for jobs.")
        return redirect(url_for("job_details", job_id=job_id))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Check whether the job exists
        cursor.execute(
            "SELECT job_id FROM jobs WHERE job_id = :job_id",
            {"job_id": job_id}
        )

        if cursor.fetchone() is None:
            flash("This job does not exist.")
            return redirect(url_for("jobs"))

        # Prevent duplicate applications
        cursor.execute(
            """
            SELECT application_id
            FROM applications
            WHERE job_id = :job_id AND applicant_id = :applicant_id
            """,
            {
                "job_id": job_id,
                "applicant_id": session["user_id"]
            }
        )

        if cursor.fetchone():
            flash("You have already applied for this job.")
            return redirect(url_for("job_details", job_id=job_id))

        cursor.execute(
            """
            INSERT INTO applications (job_id, applicant_id, application_status)
            VALUES (:job_id, :applicant_id, 'Pending')
            """,
            {
                "job_id": job_id,
                "applicant_id": session["user_id"]
            }
        )

        connection.commit()
        flash("Your application was submitted successfully!")

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Failed to submit job application")
        flash("Unable to submit your application. Please try again.")

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("job_details", job_id=job_id))  
@app.route("/my-applications")
def my_applications():
    if not session.get("user_id"):
        flash("Please log in to view your applications.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can view this page.", "error")
        return redirect(url_for("jobs"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                j.job_id,
                a.application_id,
                j.title,
                j.company_name,
                j.location,
                a.application_status,
                a.applied_at
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE a.applicant_id = :applicant_id
            ORDER BY a.applied_at DESC
            """,
            {"applicant_id": session["user_id"]}
        )

        applications = cursor.fetchall()

        return render_template(
            "my_applications.html",
            applications=applications
        )

    except Exception:
        app.logger.exception("Failed to load applications")
        flash("Unable to load your applications. Please try again.", "error")
        return redirect(url_for("jobs"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()
@app.route("/employer/applications")
def employer_applications():
    if not session.get("user_id"):
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "employer":
        flash("Only employers can view applications.", "error")
        return redirect(url_for("jobs"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                a.application_id,
                j.title,
                j.company_name,
                u.full_name,
                u.email,
                a.application_status,
                a.applied_at,
                u.resume_filename
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            JOIN users u ON a.applicant_id = u.user_id
            WHERE j.employer_id = :employer_id
            ORDER BY a.applied_at DESC
            """,
            {"employer_id": session["user_id"]}
        )

        applications = cursor.fetchall()

        return render_template(
            "employer_applications.html",
            applications=applications
        )

    except Exception:
        app.logger.exception("Failed to load employer applications")
        flash("Unable to load applications. Please try again.", "error")
        return redirect(url_for("jobs"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()
@app.route("/employer/application/<int:application_id>/resume")
def download_resume(application_id):
    if not session.get("user_id"):
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "employer":
        flash("Only employers can download applicant resumes.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT u.resume_filename
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            JOIN users u ON a.applicant_id = u.user_id
            WHERE a.application_id = :application_id
              AND j.employer_id = :employer_id
            """,
            {
                "application_id": application_id,
                "employer_id": session["user_id"]
            }
        )

        result = cursor.fetchone()

        if result is None:
            flash("Application not found or access denied.", "error")
            return redirect(url_for("employer_applications"))

        resume_filename = result[0]

        if not resume_filename:
            flash("This applicant has not uploaded a resume.", "error")
            return redirect(url_for("employer_applications"))

        # Prevent directory traversal through a database filename.
        if os.path.basename(resume_filename) != resume_filename:
            app.logger.warning("Invalid resume filename in database")
            flash("Invalid resume file.", "error")
            return redirect(url_for("employer_applications"))

        resume_path = os.path.join(UPLOAD_FOLDER, resume_filename)

        if not os.path.isfile(resume_path):
            flash("The resume file could not be found.", "error")
            return redirect(url_for("employer_applications"))

        return send_from_directory(
            directory=UPLOAD_FOLDER,
            path=resume_filename,
            as_attachment=True
        )

    except Exception:
        app.logger.exception("Failed to download applicant resume")
        flash("Unable to download the resume. Please try again.", "error")
        return redirect(url_for("employer_applications"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()            
@app.route("/employer/application/<int:application_id>/update", methods=["POST"])
def update_application_status(application_id):
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "employer":
        flash("Only employers can update application statuses.", "error")
        return redirect(url_for("home"))

    new_status = request.form.get("status", "").strip()

    allowed_statuses = {
        "Reviewed",
        "Shortlisted",
        "Rejected",
        "Accepted"
    }

    if new_status not in allowed_statuses:
        flash("Invalid application status.", "error")
        return redirect(url_for("employer_applications"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Find the application and verify that it belongs to this employer.
        cursor.execute("""
            SELECT
                a.applicant_id,
                j.title,
                j.company_name,
                a.application_status
            FROM applications a
            JOIN jobs j ON a.job_id = j.job_id
            WHERE a.application_id = :application_id
              AND j.employer_id = :employer_id
        """, {
            "application_id": application_id,
            "employer_id": session["user_id"]
        })

        application = cursor.fetchone()

        if application is None:
            connection.rollback()
            flash("Application not found or access denied.", "error")
            return redirect(url_for("employer_applications"))

        applicant_id = application[0]
        job_title = application[1]
        company_name = application[2]
        current_status = application[3]

        if current_status == "Withdrawn":
            connection.rollback()
            flash("A withdrawn application cannot be updated.", "error")
            return redirect(url_for("employer_applications"))

        if current_status == new_status:
            connection.rollback()
            flash("The application already has this status.", "error")
            return redirect(url_for("employer_applications"))

        # Update the application status.
        cursor.execute("""
            UPDATE applications
            SET application_status = :new_status
            WHERE application_id = :application_id
              AND job_id IN (
                  SELECT job_id
                  FROM jobs
                  WHERE employer_id = :employer_id
              )
        """, {
            "new_status": new_status,
            "application_id": application_id,
            "employer_id": session["user_id"]
        })

        # Create a notification for the job seeker.
        message = (
            f"Your application for {job_title} at {company_name} "
            f"has been updated to {new_status}."
        )

        cursor.execute("""
            INSERT INTO notifications (
                user_id,
                application_id,
                message
            )
            VALUES (
                :user_id,
                :application_id,
                :message
            )
        """, {
            "user_id": applicant_id,
            "application_id": application_id,
            "message": message
        })

        # Save both changes together.
        connection.commit()

        flash(
            f"Application status updated to {new_status}. "
            "A notification has been sent to the job seeker.",
            "success"
        )

    except oracledb.Error:
        if connection:
            connection.rollback()

        app.logger.exception(
            "Error updating application status and creating notification"
        )

        flash(
            "Unable to update the application status. Please try again.",
            "error"
        )

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("employer_applications"))
@app.route("/job-seeker/dashboard")
def job_seeker_dashboard():
    if "user_id" not in session or session.get("role") != "job_seeker":
        flash("Please log in as a job seeker.", "error")
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get application statistics
        cursor.execute("""
            SELECT
                COUNT(*),
                SUM(CASE
                    WHEN application_status = 'Pending' THEN 1
                    ELSE 0
                END),
                SUM(CASE
                    WHEN application_status = 'Shortlisted' THEN 1
                    ELSE 0
                END)
            FROM applications
            WHERE applicant_id = :user_id
        """, {"user_id": session["user_id"]})

        stats = cursor.fetchone()

        # Get the five most recent applications
        cursor.execute("""
            SELECT *
            FROM (
                SELECT
                    j.title,
                    j.company_name,
                    j.location,
                    a.application_status,
                    a.applied_at
                FROM applications a
                JOIN jobs j ON a.job_id = j.job_id
                WHERE a.applicant_id = :user_id
                ORDER BY a.applied_at DESC
            )
            WHERE ROWNUM <= 5
        """, {"user_id": session["user_id"]})

        recent_applications = cursor.fetchall()

        return render_template(
            "job_seeker_dashboard.html",
            stats=stats,
            recent_applications=recent_applications
        )

    except oracledb.Error:
        app.logger.exception("Failed to load job seeker dashboard")
        flash("Unable to load your dashboard. Please try again.", "error")
        return redirect(url_for("jobs"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()
@app.route("/upload-resume", methods=["GET", "POST"])
def upload_resume():
    if not session.get("user_id"):
        flash("Please log in to upload your resume.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can upload resumes.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        uploaded_file = request.files.get("resume")

        if not uploaded_file or not uploaded_file.filename:
            flash("Please select a PDF resume.", "error")
            return redirect(url_for("upload_resume"))

        filename = secure_filename(uploaded_file.filename)

        if not filename or "." not in filename:
            flash("Invalid filename.", "error")
            return redirect(url_for("upload_resume"))

        extension = filename.rsplit(".", 1)[1].lower()

        if extension != "pdf":
            flash("Only PDF files are allowed.", "error")
            return redirect(url_for("upload_resume"))

        # Use a unique filename to avoid overwriting other users' files.
        stored_filename = f"user_{session['user_id']}_{filename}"

        connection = None
        cursor = None
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], stored_filename)

        try:
            # Save the new resume temporarily.
            uploaded_file.save(file_path)

            # Confirm the file begins with the PDF signature.
            with open(file_path, "rb") as resume_file:
                if not resume_file.read(5).startswith(b"%PDF-"):
                    os.remove(file_path)
                    flash("The selected file is not a valid PDF.", "error")
                    return redirect(url_for("upload_resume"))

            connection = get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE users
                SET resume_filename = :resume_filename
                WHERE user_id = :user_id
                  AND role = 'job_seeker'
                """,
                {
                    "resume_filename": stored_filename,
                    "user_id": session["user_id"]
                }
            )

            if cursor.rowcount == 0:
                connection.rollback()
                os.remove(file_path)
                flash("Unable to find your job seeker account.", "error")
                return redirect(url_for("upload_resume"))

            connection.commit()
            flash("Resume uploaded successfully!", "success")
            return redirect(url_for("job_seeker_dashboard"))

        except Exception:
            if connection:
                connection.rollback()

            # Remove the newly uploaded file if the operation fails.
            if os.path.exists(file_path):
                os.remove(file_path)

            app.logger.exception("Resume upload failed")
            flash("Unable to upload your resume. Please try again.", "error")

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("upload_resume.html")


@app.route("/profile")
def profile():
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can access this profile.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT user_id, full_name, email, role,
                   resume_filename, skills
            FROM users
            WHERE user_id = :user_id
        """, {"user_id": session["user_id"]})

        user = cursor.fetchone()

        if user is None:
            flash("Profile not found.", "error")
            return redirect(url_for("job_seeker_dashboard"))

        return render_template("profile.html", user=user)

    except oracledb.Error:
        app.logger.exception("Error loading profile")
        flash("Unable to load your profile.", "error")
        return redirect(url_for("job_seeker_dashboard"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()
          


@app.route("/update-profile", methods=["POST"])
def update_profile():
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can update their profile.", "error")
        return redirect(url_for("home"))

    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    skills = request.form.get("skills", "").strip()

    if not full_name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for("profile"))

    if len(skills) > 1000:
        flash("Skills cannot exceed 1000 characters.", "error")
        return redirect(url_for("profile"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Check whether another user already uses this email
        cursor.execute("""
            SELECT user_id
            FROM users
            WHERE LOWER(email) = :email
              AND user_id <> :user_id
        """, {
            "email": email,
            "user_id": session["user_id"]
        })

        if cursor.fetchone():
            flash("This email is already registered.", "error")
            return redirect(url_for("profile"))

        # Update the user's profile and skills
        cursor.execute("""
            UPDATE users
            SET full_name = :full_name,
                email = :email,
                skills = :skills
            WHERE user_id = :user_id
        """, {
            "full_name": full_name,
            "email": email,
            "skills": skills or None,
            "user_id": session["user_id"]
        })

        if cursor.rowcount != 1:
            connection.rollback()
            flash("Profile not found. Please log in again.", "error")
            return redirect(url_for("profile"))

        connection.commit()

        session["full_name"] = full_name
        session["email"] = email

        flash("Profile and skills updated successfully!", "success")
        return redirect(url_for("profile"))

    except oracledb.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Profile update failed")
        flash("Database error while updating your profile. Check the Flask terminal.", "error")
        return redirect(url_for("profile"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    # Make sure the user is logged in
    if not session.get("user_id"):
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate the new password
        if not current_password or not new_password or not confirm_password:
            flash("All password fields are required.", "error")
            return redirect(url_for("change_password"))

        if len(new_password) < 8:
            flash("Your new password must contain at least 8 characters.", "error")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("The new passwords do not match.", "error")
            return redirect(url_for("change_password"))

        connection = None
        cursor = None

        try:
            connection = get_connection()
            cursor = connection.cursor()

            # Retrieve the current password hash
            cursor.execute(
                """
                SELECT password_hash
                FROM users
                WHERE user_id = :user_id
                """,
                {"user_id": session["user_id"]}
            )

            result = cursor.fetchone()

            if result is None:
                flash("User account not found.", "error")
                return redirect(url_for("login"))

            stored_password_hash = result[0]

            # Verify the current password
            if not check_password_hash(stored_password_hash, current_password):
                flash("Your current password is incorrect.", "error")
                return redirect(url_for("change_password"))

            # Store a hash of the new password, never the plain text
            new_password_hash = generate_password_hash(new_password)

            cursor.execute(
                """
                UPDATE users
                SET password_hash = :password_hash
                WHERE user_id = :user_id
                """,
                {
                    "password_hash": new_password_hash,
                    "user_id": session["user_id"]
                }
            )

            connection.commit()

            flash("Password changed successfully!", "success")
            return redirect(url_for("change_password"))

        except Exception:
            if connection:
                connection.rollback()

            app.logger.exception("Failed to change password")
            flash("Unable to change your password. Please try again.", "error")

        finally:
            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("change_password.html")

@app.route("/withdraw-application/<int:application_id>", methods=["POST"])
def withdraw_application(application_id):
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can withdraw applications.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE applications
            SET application_status = 'Withdrawn'
            WHERE application_id = :application_id
              AND applicant_id = :applicant_id
              AND application_status IN ('Pending', 'Reviewed')
        """, {
            "application_id": application_id,
            "applicant_id": session["user_id"]
        })

        if cursor.rowcount == 1:
            connection.commit()
            flash("Your application has been withdrawn successfully.", "success")
        else:
            connection.rollback()
            flash(
                "Application could not be withdrawn. It may already be processed "
                "or may not belong to your account.",
                "error"
            )

    except oracledb.Error:
        if connection:
            connection.rollback()
        app.logger.exception("Database error while withdrawing application")
        flash("Unable to withdraw your application right now.", "error")

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("my_applications"))
@app.route("/notifications")
def notifications():
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Notifications are available to job seekers.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                notification_id,
                message,
                is_read,
                created_at,
                application_id
            FROM notifications
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """, {"user_id": session["user_id"]})

        notification_rows = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*)
            FROM notifications
            WHERE user_id = :user_id
              AND is_read = 0
        """, {"user_id": session["user_id"]})

        unread_count = cursor.fetchone()[0]

        return render_template(
            "notifications.html",
            notifications=notification_rows,
            unread_count=unread_count
        )

    except oracledb.Error:
        app.logger.exception("Error loading notifications")
        flash("Unable to load notifications right now.", "error")
        return redirect(url_for("job_seeker_dashboard"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id):
    if "user_id" not in session:
        flash("Please log in to continue.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Only job seekers can manage these notifications.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            UPDATE notifications
            SET is_read = 1
            WHERE notification_id = :notification_id
              AND user_id = :user_id
        """, {
            "notification_id": notification_id,
            "user_id": session["user_id"]
        })

        if cursor.rowcount == 1:
            connection.commit()
            flash("Notification marked as read.", "success")
        else:
            connection.rollback()
            flash("Notification not found.", "error")

    except oracledb.Error:
        if connection:
            connection.rollback()

        app.logger.exception("Error marking notification as read")
        flash("Unable to update the notification.", "error")

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("notifications"))


@app.route("/recommended-jobs")
def recommended_jobs():
    if "user_id" not in session:
        flash("Please log in to view recommended jobs.", "error")
        return redirect(url_for("login"))

    if session.get("role") != "job_seeker":
        flash("Job recommendations are available to job seekers.", "error")
        return redirect(url_for("home"))

    connection = None
    cursor = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        # Get the job seeker's skills
        cursor.execute("""
            SELECT skills
            FROM users
            WHERE user_id = :user_id
        """, {"user_id": session["user_id"]})

        user_row = cursor.fetchone()

        if not user_row or not user_row[0]:
            flash(
                "Please add your skills to your profile first.",
                "error"
            )
            return redirect(url_for("profile"))

        user_skills = {
            skill.strip().casefold()
            for skill in user_row[0].split(",")
            if skill.strip()
        }

        # Get available job listings
        cursor.execute("""
            SELECT job_id, title, company_name, location,
                   required_skills, salary, posted_at
            FROM jobs
            ORDER BY posted_at DESC
        """)

        job_rows = cursor.fetchall()
        recommendations = []

        for job in job_rows:
            required_skills_text = job[4] or ""

            required_skills = {
                skill.strip().casefold()
                for skill in required_skills_text.split(",")
                if skill.strip()
            }

            # Avoid division by zero for jobs without required skills
            if not required_skills:
                match_percentage = 0
                matched_skills = []
            else:
                matched_skills = sorted(user_skills & required_skills)
                match_percentage = round(
                    len(matched_skills) / len(required_skills) * 100,
                    2
                )

            recommendations.append({
                "job_id": job[0],
                "title": job[1],
                "company": job[2],
                "location": job[3],
                "required_skills": required_skills_text,
                "salary": job[5],
                "posted_at": job[6],
                "match_percentage": match_percentage,
                "matched_skills": matched_skills
            })

        # Show jobs with the highest match first
        recommendations.sort(
            key=lambda job: job["match_percentage"],
            reverse=True
        )

        return render_template(
            "recommended_jobs.html",
            recommendations=recommendations,
            user_skills=sorted(user_skills)
        )

    except oracledb.Error:
        app.logger.exception("Error generating job recommendations")
        flash("Unable to generate job recommendations.", "error")
        return redirect(url_for("job_seeker_dashboard"))

    finally:
        if cursor:
            cursor.close()

        if connection:
            connection.close()


if __name__ == "__main__":
    app.run(debug=True)

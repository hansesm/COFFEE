from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('home', '0009_remove_course_managing_groups_course_editing_groups_and_more'),
    ]

    operations = [
        # Course performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_faculty ON home_course(faculty);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_faculty;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_study_programme ON home_course(study_programme);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_study_programme;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_chair ON home_course(chair);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_chair;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_term ON home_course(term);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_term;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_name ON home_course(course_name);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_name;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_active ON home_course(active);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_active;"
        ),
        
        # Task performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_task_active ON home_task(active);",
            reverse_sql="DROP INDEX IF EXISTS idx_task_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_task_course_active ON home_task(course_id, active);",
            reverse_sql="DROP INDEX IF EXISTS idx_task_course_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_task_title ON home_task(title);",
            reverse_sql="DROP INDEX IF EXISTS idx_task_title;"
        ),
        
        # Criteria performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_criteria_active ON home_criteria(active);",
            reverse_sql="DROP INDEX IF EXISTS idx_criteria_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_criteria_course_active ON home_criteria(course_id, active);",
            reverse_sql="DROP INDEX IF EXISTS idx_criteria_course_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_criteria_title ON home_criteria(title);",
            reverse_sql="DROP INDEX IF EXISTS idx_criteria_title;"
        ),
        
        # Feedback performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedback_active ON home_feedback(active);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedback_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedback_course_active ON home_feedback(course_id, active);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedback_course_active;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedback_task ON home_feedback(task_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedback_task;"
        ),
        
        # FeedbackSession performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbacksession_timestamp ON home_feedbacksession(timestamp);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbacksession_timestamp;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbacksession_course ON home_feedbacksession(course_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbacksession_course;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbacksession_feedback ON home_feedbacksession(feedback_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbacksession_feedback;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbacksession_staff ON home_feedbacksession(staff_user);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbacksession_staff;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbacksession_session_key ON home_feedbacksession(session_key);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbacksession_session_key;"
        ),
        
        # FeedbackCriteria performance indexes
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbackcriteria_feedback_rank ON home_feedbackcriteria(feedback_id, rank);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbackcriteria_feedback_rank;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_feedbackcriteria_criteria ON home_feedbackcriteria(criteria_id);",
            reverse_sql="DROP INDEX IF EXISTS idx_feedbackcriteria_criteria;"
        ),
        
        # Composite indexes for common query patterns
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_faculty_programme ON home_course(faculty, study_programme);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_faculty_programme;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS idx_course_active_faculty ON home_course(active, faculty);",
            reverse_sql="DROP INDEX IF EXISTS idx_course_active_faculty;"
        ),
    ]

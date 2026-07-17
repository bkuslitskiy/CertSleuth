"""SEC-008: row-level security beneath app scoping. No-op on sqlite dev.
The app connects as a non-superuser role; each request SETs certsleuth.user_id
(see core middleware TODO) so a missed WHERE clause cannot cross tenants."""
from django.db import migrations

FORWARD = """
ALTER TABLE tracker_usercertification ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracker_activity ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracker_usergoal ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_isolation_uc ON tracker_usercertification
  USING (user_id = current_setting('certsleuth.user_id', true)::bigint);
CREATE POLICY user_isolation_act ON tracker_activity
  USING (user_id = current_setting('certsleuth.user_id', true)::bigint);
CREATE POLICY user_isolation_goal ON tracker_usergoal
  USING (user_id = current_setting('certsleuth.user_id', true)::bigint);
"""

REVERSE = """
DROP POLICY IF EXISTS user_isolation_uc ON tracker_usercertification;
DROP POLICY IF EXISTS user_isolation_act ON tracker_activity;
DROP POLICY IF EXISTS user_isolation_goal ON tracker_usergoal;
ALTER TABLE tracker_usercertification DISABLE ROW LEVEL SECURITY;
ALTER TABLE tracker_activity DISABLE ROW LEVEL SECURITY;
ALTER TABLE tracker_usergoal DISABLE ROW LEVEL SECURITY;
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(FORWARD)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVERSE)


class Migration(migrations.Migration):
    dependencies = [("tracker", "0001_initial")]
    operations = [migrations.RunPython(forward, reverse)]

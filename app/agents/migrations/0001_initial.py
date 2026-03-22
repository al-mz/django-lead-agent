import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentAuditLog",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ("object_id", models.UUIDField()),
                ("run_id", models.UUIDField()),
                ("tool_use_id", models.CharField(max_length=255)),
                ("tool_name", models.CharField(max_length=255)),
                ("tool_input", models.JSONField()),
                ("tool_output", models.TextField(blank=True, null=True)),
                ("duration_ms", models.IntegerField(null=True)),
                ("logged_at", models.DateTimeField(auto_now_add=True)),
                (
                    "content_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "ordering": ["logged_at"],
            },
        ),
        migrations.AddIndex(
            model_name="agentauditlog",
            index=models.Index(
                fields=["content_type", "object_id", "logged_at"],
                name="agents_agen_content_50d8e8_idx",
            ),
        ),
    ]

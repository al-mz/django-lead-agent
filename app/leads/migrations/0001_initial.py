import uuid
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentConfig",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(help_text="Display name for this config", max_length=255)),
                (
                    "is_active",
                    models.BooleanField(
                        default=False,
                        help_text="Only one config may be active at a time.",
                    ),
                ),
                ("company_name", models.CharField(max_length=255)),
                (
                    "company_description",
                    models.TextField(
                        help_text="What your company does. Injected into the agent system prompt."
                    ),
                ),
                (
                    "ideal_customer_description",
                    models.TextField(
                        help_text="Plain English description of your ideal customer. The agent uses this to score leads."
                    ),
                ),
                (
                    "disqualifying_signals",
                    models.TextField(
                        help_text="Signals that make a lead cold regardless of other factors. E.g. 'Students, hobbyists, companies with fewer than 10 employees.'"
                    ),
                ),
                (
                    "scoring_guidance",
                    models.TextField(
                        help_text="Additional scoring instructions. E.g. 'Weight payment-related urgency higher than generic interest.'"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Agent Config",
                "verbose_name_plural": "Agent Configs",
            },
        ),
        migrations.CreateModel(
            name="Contact",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(unique=True)),
                ("company", models.CharField(max_length=255)),
                (
                    "email_domain",
                    models.CharField(
                        db_index=True,
                        help_text="Derived from email on save. Used for domain-based CRM lookup.",
                        max_length=255,
                    ),
                ),
                ("role", models.CharField(blank=True, max_length=255)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="ProductInfo",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False),
                ),
                ("title", models.CharField(max_length=500)),
                ("content", models.TextField()),
                ("keywords", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="RoutingRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(help_text='E.g. "hot", "warm", "cold"', max_length=100)),
                ("score_min", models.FloatField()),
                ("score_max", models.FloatField()),
                ("queue_name", models.CharField(max_length=255)),
                (
                    "response_sla_minutes",
                    models.IntegerField(
                        help_text="Minutes until first human touch is required."
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["-score_min"],
            },
        ),
        migrations.CreateModel(
            name="Lead",
            fields=[
                (
                    "id",
                    models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField()),
                ("company", models.CharField(max_length=255)),
                ("role", models.CharField(blank=True, max_length=255)),
                (
                    "message",
                    models.TextField(
                        help_text="Max 5000 characters.",
                        validators=[django.core.validators.MaxLengthValidator(5000)],
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        help_text='E.g. "website", "referral"',
                        max_length=100,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("new", "New"),
                            ("qualifying", "Qualifying"),
                            ("qualified", "Qualified"),
                            ("disqualified", "Disqualified"),
                            ("failed", "Failed"),
                        ],
                        default="new",
                        max_length=20,
                    ),
                ),
                ("qualification_result", models.JSONField(blank=True, null=True)),
                ("routing_queue", models.CharField(blank=True, max_length=255, null=True)),
                ("response_sla_deadline", models.DateTimeField(blank=True, null=True)),
                ("draft_reply", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(
                fields=["status", "-created_at"], name="leads_lead_status_bca4e1_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="lead",
            index=models.Index(fields=["email"], name="leads_lead_email_d1e060_idx"),
        ),
    ]

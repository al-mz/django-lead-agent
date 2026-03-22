from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from leads.models import Lead


@receiver(post_save, sender=Lead)
def trigger_qualify_on_new_lead(sender, instance, created, **kwargs):
    """Queue qualification only after the lead creation transaction commits."""
    if created and instance.status == Lead.Status.NEW:
        from leads.tasks import qualify_lead_task

        transaction.on_commit(
            lambda: qualify_lead_task.delay(str(instance.id)),
            using=instance._state.db,
        )

from django.core.management.base import BaseCommand
from pt_backend.models import CaseUploadBatch
from expert_user_feature.services import build_or_refresh_dataset_from_batch

class Command(BaseCommand):
    help = "Backfill ExpertDataset & rows dari seluruh CaseUploadBatch yang ada."

    def handle(self, *args, **opts):
        created = 0
        for batch in CaseUploadBatch.objects.all():
            build_or_refresh_dataset_from_batch(batch)
            created += 1
        self.stdout.write(self.style.SUCCESS(f"Synced {created} batch(es) into ExpertDataset."))

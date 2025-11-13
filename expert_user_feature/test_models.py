from django.test import TestCase
from django.utils import timezone
from expert_user_feature.models import ExpertDataset, ExpertDatasetRow

class ExpertDatasetModelTests(TestCase):
    def test_str_returns_id_and_filename(self):
        ds = ExpertDataset.objects.create(
        data_id="ID1",
        file_name="Survey_Bandung.csv",
        last_edited=timezone.now(),
        submitted_by="EXPERTA",
        )
        self.assertEqual(str(ds), "ID1 • Survey_Bandung.csv")

class ExpertDatasetRowModelTests(TestCase):
    def setUp(self):
        self.ds = ExpertDataset.objects.create(
        data_id="ID2",
        file_name="Report_Jakarta.xlsx",
        last_edited=timezone.now(),
        submitted_by="EXPERTB",
        )

    def test_rows_related_name_and_ordering(self):
        # Insert out of order
        ExpertDatasetRow.objects.create(
            dataset=self.ds, row_number=3, data_id="R3",
            gender="lainnya", age=14, city="jakarta",
            status="status c", disease_id="IDA", location_id="IDB",
            severity="severity c",
        )
        ExpertDatasetRow.objects.create(
            dataset=self.ds, row_number=1, data_id="R1",
            gender="perempuan", age=14, city="jakarta",
            status="status a", disease_id="IDA", location_id="IDB",
            severity="severity a",
        )
        ExpertDatasetRow.objects.create(
            dataset=self.ds, row_number=2, data_id="R2",
            gender="laki-laki", age=14, city="jakarta",
            status="status b", disease_id="IDA", location_id="IDB",
            severity="severity b",
        )

        rows = list(self.ds.rows.all())
        self.assertEqual([r.row_number for r in rows], [1, 2, 3])
        self.assertEqual([r.data_id for r in rows], ["R1", "R2", "R3"])

    def test_payload_is_optional(self):
        row = ExpertDatasetRow.objects.create(
            dataset=self.ds, row_number=1, data_id="R1",
            gender="perempuan", age=20, city="jakarta",
            status="ok", disease_id="IDA", location_id="IDB",
            severity="ringan", payload=None,
        )
        self.assertIsNone(row.payload)
from odoo.tests.common import TransactionCase


class TestCFDISeries(TransactionCase):
    def test_create_method(self):
        # Create a CFDISeries record without implementation provided
        series = self.env["l10n_mx_cfdi.series"].create(
            {"name": "Test Series", "code": "TEST"}
        )

        # Check if the implementation is set to "no_gap"
        self.assertEqual(series.implementation, "no_gap")

    def test_create_method_with_implementation(self):
        # Create a CFDISeries record with implementation provided
        series = self.env["l10n_mx_cfdi.series"].create(
            {"name": "Test Series", "code": "TEST", "implementation": "standard"}
        )

        # Check if the implementation is set to the provided value
        self.assertEqual(series.implementation, "standard")

    def test_create_batch_sets_implementation_on_each_record(self):
        series = self.env["l10n_mx_cfdi.series"].create(
            [
                {"name": "Series A", "code": "A"},
                {"name": "Series B", "code": "B", "implementation": "standard"},
            ]
        )
        self.assertEqual(series.mapped("implementation"), ["no_gap", "standard"])

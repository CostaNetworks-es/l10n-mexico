from base64 import b64encode
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon

CFDI_STAMP = {
    "Status": "active",
    "Id": "tracking-id",
    "Complement": {"TaxStamp": {"Uuid": "11111111-2222-3333-4444-555555555555"}},
}


@tagged("post_install", "-at_install")
class TestAccountPaymentCFDI(AccountTestInvoicingCommon):
    """Payments carry their own CFDI data: in 18.0 account.payment no longer
    delegates (_inherits) to account.move."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.company.l10n_mx_cfdi_auto = True
        cls.payment_form = cls.env.ref("l10n_mx_catalogs.c_forma_pago_01")
        cls.ppd = cls.env.ref("l10n_mx_catalogs.c_metodo_pago_PPD")
        cls.regimen = cls.env.ref("l10n_mx_catalogs.c_regimen_fiscal_601")
        cls.service = cls.env["l10n_mx_cfdi.cfdi_service"].create(
            {"name": "Test service", "user": "test_user", "password": "test_password"}
        )
        cls.issuer = cls.env["l10n_mx_cfdi.issuer"].create(
            {
                "name": "Test Issuer",
                "vat": "RFC123456",
                "zip": "77500",
                "tax_regime": cls.regimen.id,
                "certificate_file": b64encode(b"certificate"),
                "key_file": b64encode(b"key"),
                "key_password": "password",
                "service_id": cls.service.id,
            }
        )
        cls.partner_a.write(
            {"vat": "XEXX010101000", "zip": "77500", "tax_regime": cls.regimen.id}
        )

    def _mock_pac_stamp(self):
        """Replace the PAC call with a successful stamp.

        Patched on the registry class (the most derived one) so the mock also
        holds when another module overrides ``create_cfdi`` without calling super.
        """
        return patch.object(
            type(self.env["l10n_mx_cfdi.cfdi_service"]),
            "create_cfdi",
            return_value=CFDI_STAMP,
        )

    def _create_document(self, **extra):
        vals = {
            "issuer_id": self.issuer.id,
            "receiver_id": self.partner_a.id,
            "serie": "TST",
            "folio": str(self.env["l10n_mx_cfdi.document"].search_count([]) + 1),
        }
        vals.update(extra)
        return self.env["l10n_mx_cfdi.document"].create(vals)

    def _create_payment(self, **extra):
        vals = {
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner_a.id,
            "amount": 50.0,
            "journal_id": self.company_data["default_journal_bank"].id,
        }
        vals.update(extra)
        return self.env["account.payment"].create(vals)

    def _post_invoice_with_cfdi(self):
        """Posted invoice, deferred payment method, already stamped."""
        invoice = self.init_invoice(
            "out_invoice", products=self.product_a, post=True, amounts=[100.0]
        )
        invoice.write(
            {
                "cfdi_required": True,
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner_a.id,
                "payment_method_id": self.ppd.id,
                "payment_form_id": self.payment_form.id,
                "cfdi_use_id": self.env.ref("l10n_mx_catalogs.c_uso_cfdi_G03").id,
            }
        )
        invoice_cfdi = self._create_document(
            type="I", related_invoice_id=invoice.id, state="published", uuid="INV-UUID"
        )
        invoice.related_cert_ids = invoice_cfdi
        return invoice

    def _register_payment(self, invoice, amount=None):
        wizard = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create(
                {
                    "payment_form_id": self.payment_form.id,
                    "amount": amount or invoice.amount_residual,
                    "journal_id": self.company_data["default_journal_bank"].id,
                }
            )
        )
        return wizard._create_payments()

    def test_payment_form_is_stored_on_the_payment(self):
        payment = self._create_payment(payment_form_id=self.payment_form.id)
        self.assertEqual(payment.payment_form_id, self.payment_form)

    def test_register_payment_wizard_passes_payment_form_to_the_payment(self):
        invoice = self.init_invoice(
            "out_invoice", products=self.product_a, post=True, amounts=[100.0]
        )
        payment = self._register_payment(invoice)
        self.assertEqual(payment.payment_form_id, self.payment_form)

    def test_cfdi_document_is_the_published_payment_cfdi(self):
        payment = self._create_payment()
        published = self._create_document(
            type="P", related_payment_id=payment.id, state="published"
        )
        draft_of_other_type = self._create_document(type="I", state="published")
        payment.related_cert_ids = published | draft_of_other_type
        self.assertEqual(payment.cfdi_document_id, published)

    def test_cfdi_document_ignores_not_published_documents(self):
        payment = self._create_payment()
        canceled = self._create_document(
            type="P", related_payment_id=payment.id, state="canceled"
        )
        payment.related_cert_ids = canceled
        self.assertFalse(payment.cfdi_document_id)

    def test_cfdi_document_state_follows_the_document(self):
        payment = self._create_payment()
        published = self._create_document(
            type="P", related_payment_id=payment.id, state="published"
        )
        payment.related_cert_ids = published
        self.assertEqual(payment.cfdi_document_state, "published")

    def test_cfdi_fields_are_not_copied_to_the_duplicated_payment(self):
        payment = self._create_payment(payment_form_id=self.payment_form.id)
        published = self._create_document(
            type="P", related_payment_id=payment.id, state="published"
        )
        payment.related_cert_ids = published
        copy = payment.copy()
        self.assertFalse(copy.related_cert_ids)
        self.assertFalse(copy.cfdi_document_id)

    def test_generate_cfdi_requires_a_reconciled_payment(self):
        payment = self._create_payment()
        payment.action_post()
        with self.assertRaises(ValidationError):
            payment.action_generate_cfdi()

    def test_generate_cfdi_refuses_a_payment_that_already_has_cfdi(self):
        payment = self._create_payment()
        payment.related_cert_ids = self._create_document(
            type="P", related_payment_id=payment.id, state="published"
        )
        with self.assertRaises(ValidationError):
            payment.action_generate_cfdi()

    def test_reconciling_a_payment_creates_its_payment_cfdi(self):
        invoice = self._post_invoice_with_cfdi()
        with self._mock_pac_stamp() as create_cfdi:
            payment = self._register_payment(invoice)
        self.assertEqual(create_cfdi.call_count, 1)
        self.assertEqual(payment.cfdi_document_id.type, "P")
        self.assertEqual(payment.cfdi_document_id.related_payment_id, payment)
        self.assertEqual(payment.cfdi_document_id.state, "published")
        self.assertIn(payment.cfdi_document_id, invoice.related_cert_ids)

    def test_payment_cfdi_data_uses_the_payment_form_of_the_payment(self):
        invoice = self._post_invoice_with_cfdi()
        with self._mock_pac_stamp():
            payment = self._register_payment(invoice)
        data = payment.prepare_payment_cfdi()
        self.assertEqual(data["PaymentForm"], self.payment_form.code)
        self.assertEqual(data["Amount"], invoice.amount_total)
        self.assertEqual(data["RelatedDocuments"][0]["Uuid"], "INV-UUID")

    def test_unreconciling_a_payment_cancels_its_payment_cfdi(self):
        invoice = self._post_invoice_with_cfdi()
        with self._mock_pac_stamp():
            payment = self._register_payment(invoice)
        cfdi = payment.cfdi_document_id
        with patch.object(type(cfdi), "cancel") as cancel:
            invoice.line_ids.remove_move_reconcile()
        cancel.assert_called_once_with("02")
        self.assertEqual(cfdi.related_payment_id, payment)

    def test_credit_note_cfdi_is_created_when_the_credit_note_is_reconciled(self):
        invoice = self._post_invoice_with_cfdi()
        reversal = (
            self.env["account.move.reversal"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"journal_id": invoice.journal_id.id})
        )
        refund = self.env["account.move"].browse(reversal.refund_moves()["res_id"])
        self.assertEqual(refund.move_type, "out_refund")
        self.assertTrue(refund.cfdi_required)
        # Posting a reversal reconciles it with the reversed invoice
        with self._mock_pac_stamp():
            refund.action_post()
        refund_cfdi = refund.related_cert_ids.filtered(lambda doc: doc.type == "E")
        self.assertEqual(refund_cfdi.state, "published")
        self.assertEqual(
            refund_cfdi.related_document_ids.target_id,
            invoice.cfdi_document_id,
            "The credit note CFDI must relate to the CFDI of the invoice",
        )

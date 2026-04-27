from django.db import models
from django.db.models import Sum
from config import settings


INVOICE_STATUS = (
    ("pending", "Pending"),
    ("paid", "Paid"),
    ("partially_paid", "Partially Paid"),
    ("overdue", "Overdue"),
)

PAYMENT_METHOD = (
    ("cash", "Cash"),
    ("card", "Card"),
    ("transfer", "Transfer"),
)


class Invoice(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_invoices",
        limit_choices_to={"is_superuser": True},
        null=True,
        blank=True,
    )
    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="invoices",
    )
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default="pending")
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.student}"

    @property
    def total_paid(self):
        result = self.payments.filter(status="approved").aggregate(total=Sum("amount"))
        return result["total"] or 0

    def update_status(self):
        total_paid = self.total_paid
        if total_paid >= self.amount:
            self.status = "paid"
        elif total_paid > 0:
            self.status = "partially_paid"
        else:
            self.status = "pending"
        self.save(update_fields=["status", "updated_at"])


class Payment(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_payments",
        limit_choices_to={"is_superuser": True},
        null=True,
        blank=True,
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default="cash")
    receipt = models.FileField(upload_to="receipts/", null=True, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=(
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected")
        ), 
        default="approved" # Default to approved for admin-created payments
    )
    accountant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="verified_payments",
        null=True,
        blank=True
    )
    comment = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment {self.amount} - {self.student}"
class Contract(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_contracts",
        limit_choices_to={"is_superuser": True},
        null=True,
        blank=True,
    )
    student = models.ForeignKey(
        "accounts.Student",
        on_delete=models.CASCADE,
        related_name="contracts",
    )
    contract_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=255, default="Educational Services Contract")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    document = models.FileField(upload_to="contracts/", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Contract"
        verbose_name_plural = "Contracts"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Contract {self.contract_number} - {self.student}"

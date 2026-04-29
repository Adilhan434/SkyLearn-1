from django.urls import path
from . import views

urlpatterns = [
    # Admin: Contracts
    path("contracts/", views.ContractListCreateAPIView.as_view(), name="contract-list-create"),
    path("contracts/<int:pk>/", views.ContractDetailAPIView.as_view(), name="contract-detail"),

    # Admin: Invoices
    path("invoices/", views.InvoiceListAPIView.as_view(), name="invoice-list"),
    path("invoices/create/", views.InvoiceCreateAPIView.as_view(), name="invoice-create"),
    path("invoices/<int:pk>/", views.InvoiceRetrieveAPIView.as_view(), name="invoice-detail"),
    path("invoices/<int:pk>/update/", views.InvoiceUpdateAPIView.as_view(), name="invoice-update"),
    path("invoices/<int:pk>/delete/", views.InvoiceDeleteAPIView.as_view(), name="invoice-delete"),

    # Admin: Payments
    path("payments/", views.PaymentListAPIView.as_view(), name="payment-list"),
    path("payments/create/", views.PaymentCreateAPIView.as_view(), name="payment-create"),
    path("payments/<int:pk>/delete/", views.PaymentDeleteAPIView.as_view(), name="payment-delete"),

    # Admin: Student Balance
    path("students/<int:pk>/balance/", views.StudentBalanceAPIView.as_view(), name="student-balance"),

    # Student/Parent: My Finance
    path("my/invoices/", views.MyInvoicesAPIView.as_view(), name="my-invoices"),
    path("my/payments/", views.MyPaymentsAPIView.as_view(), name="my-payments"),
    path("my/balance/", views.MyBalanceAPIView.as_view(), name="my-balance"),
    path("my/payments/upload/", views.ParentUploadReceiptAPIView.as_view(), name="payment-upload"),

    # Accountant: Hierarchy
    path("accountant/programs/", views.AccountantProgramsAPIView.as_view(), name="accountant-programs"),
    path("accountant/programs/<int:program_id>/groups/", views.AccountantProgramGroupsAPIView.as_view(), name="accountant-program-groups"),
    path("accountant/groups/<int:group_id>/students/", views.AccountantGroupStudentsAPIView.as_view(), name="accountant-group-students"),
    path("accountant/groups/<int:group_id>/create-invoices/", views.AccountantCreateGroupInvoicesAPIView.as_view(), name="accountant-create-group-invoices"),

    # Accountant: Payment verification
    path("accountant/payments/pending/", views.AccountantPendingPaymentsAPIView.as_view(), name="accountant-pending-payments"),
    path("accountant/payments/<int:pk>/verify/", views.AccountantVerifyPaymentAPIView.as_view(), name="accountant-verify-payment"),
    path("accountant/notifications/send-debt/", views.AccountantSendDebtNotificationAPIView.as_view(), name="accountant-send-debt-notification"),
    path("accountant/programs/<int:program_id>/update-fee/", views.AccountantUpdateProgramFeeAPIView.as_view(), name="accountant-update-program-fee"),
]

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.exceptions import PermissionDenied
from django.db.models import Sum

from accounts.models import Student
from .models import Invoice, Payment
from .serializers import (
    InvoiceListSerializer,
    InvoiceWriteSerializer,
    PaymentListSerializer,
    PaymentWriteSerializer,
    StudentBalanceSerializer,
)
from .permissions import IsStudentOrParent, IsAccountant
from core.models import Notification


# ===================== Admin: Invoices =====================


class InvoiceListAPIView(generics.ListAPIView):
    serializer_class = InvoiceListSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        qs = Invoice.objects.filter(admin=self.request.user)
        student_id = self.request.query_params.get("student")
        status = self.request.query_params.get("status")
        if student_id:
            qs = qs.filter(student_id=student_id)
        if status:
            qs = qs.filter(status=status)
        return qs


class InvoiceCreateAPIView(generics.CreateAPIView):
    serializer_class = InvoiceWriteSerializer
    permission_classes = [IsAdminUser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        context["admin"] = self.request.user
        return context


class InvoiceRetrieveAPIView(generics.RetrieveAPIView):
    serializer_class = InvoiceListSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        return Invoice.objects.filter(admin=self.request.user)


class InvoiceUpdateAPIView(generics.UpdateAPIView):
    serializer_class = InvoiceWriteSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        return Invoice.objects.filter(admin=self.request.user)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["admin"] = self.request.user
        return context


class InvoiceDeleteAPIView(generics.DestroyAPIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        return Invoice.objects.filter(admin=self.request.user)


# ===================== Admin: Payments =====================


class PaymentListAPIView(generics.ListAPIView):
    serializer_class = PaymentListSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        qs = Payment.objects.filter(admin=self.request.user)
        student_id = self.request.query_params.get("student")
        if student_id:
            qs = qs.filter(student_id=student_id)
        return qs


class PaymentCreateAPIView(generics.CreateAPIView):
    serializer_class = PaymentWriteSerializer
    permission_classes = [IsAdminUser]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        context["admin"] = self.request.user
        return context


class PaymentDeleteAPIView(generics.DestroyAPIView):
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        if not self.request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")
        return Payment.objects.filter(admin=self.request.user)

    def perform_destroy(self, instance):
        invoice = instance.invoice
        instance.delete()
        invoice.update_status()


# ===================== Admin: Student Balance =====================


class StudentBalanceAPIView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        if not request.user.is_superuser:
            raise PermissionDenied("Only admins can access this view.")

        try:
            student = Student.objects.get(pk=pk, admin=request.user)
        except Student.DoesNotExist:
            return Response({"detail": "Student not found."}, status=404)

        total_charged = (
            Invoice.objects.filter(student=student, admin=request.user).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        total_paid = (
            Payment.objects.filter(student=student, admin=request.user).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )

        data = {
            "student_id": student.pk,
            "student_name": student.get_full_name(),
            "total_charged": total_charged,
            "total_paid": total_paid,
            "balance": total_charged - total_paid,
        }
        serializer = StudentBalanceSerializer(data)
        return Response(serializer.data)


# ===================== Student: My Finance =====================


class MyInvoicesAPIView(generics.ListAPIView):
    serializer_class = InvoiceListSerializer
    permission_classes = [IsStudentOrParent]
    
    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'student_profile'):
            return Invoice.objects.filter(student=user.student_profile)
        elif user.is_parent:
            from accounts.models import Parent
            student_ids = Parent.objects.filter(user=user).values_list('student_id', flat=True)
            return Invoice.objects.filter(student_id__in=student_ids)
        return Invoice.objects.none()


class MyPaymentsAPIView(generics.ListAPIView):
    serializer_class = PaymentListSerializer
    permission_classes = [IsStudentOrParent]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, 'student_profile'):
            return Payment.objects.filter(student=user.student_profile)
        elif user.is_parent:
            from accounts.models import Parent
            student_ids = Parent.objects.filter(user=user).values_list('student_id', flat=True)
            return Payment.objects.filter(student_id__in=student_ids)
        return Payment.objects.none()


class MyBalanceAPIView(APIView):
    permission_classes = [IsStudentOrParent]

    def get(self, request):
        user = request.user
        if hasattr(user, 'student_profile'):
            students = [user.student_profile]
        elif user.is_parent:
            from accounts.models import Parent
            students = [p.student for p in Parent.objects.filter(user=user) if p.student]
        else:
            return Response({"detail": "No student profile found."}, status=404)

        results = []
        for student in students:
            total_charged = (
                Invoice.objects.filter(student=student).aggregate(total=Sum("amount"))["total"] or 0
            )
            total_paid = (
                Payment.objects.filter(student=student).aggregate(total=Sum("amount"))["total"] or 0
            )
            results.append({
                "student_id": student.pk,
                "student_name": student.get_full_name(),
                "total_charged": total_charged,
                "total_paid": total_paid,
                "balance": total_charged - total_paid,
            })
        
        if user.is_parent:
            return Response(results) # Multiple results for parents
        return Response(results[0]) # Single result for students

# ===================== Accountant: Hierarchical Financial Management =====================

class AccountantProgramsAPIView(APIView):
    """List all programs with group/student counts and financial summary."""
    permission_classes = [IsAccountant]

    def get(self, request):
        from core.models import Program
        from accounts.models import Group as StudentGroup
        programs = Program.objects.all()
        data = []
        for program in programs:
            groups = StudentGroup.objects.filter(program=program)
            student_count = Student.objects.filter(group__in=groups).count()
            total_charged = Invoice.objects.filter(student__group__in=groups).aggregate(total=Sum("amount"))["total"] or 0
            total_paid = Payment.objects.filter(student__group__in=groups, status="approved").aggregate(total=Sum("amount"))["total"] or 0
            data.append({
                "id": program.id,
                "name": program.name,
                "group_count": groups.count(),
                "student_count": student_count,
                "total_charged": float(total_charged),
                "total_paid": float(total_paid),
                "total_debt": float(total_charged) - float(total_paid),
            })
        return Response(data)


class AccountantProgramGroupsAPIView(APIView):
    """List all groups in a program with financial summary."""
    permission_classes = [IsAccountant]

    def get(self, request, program_id):
        from accounts.models import Group as StudentGroup
        groups = StudentGroup.objects.filter(program_id=program_id)
        data = []
        for group in groups:
            students = Student.objects.filter(group=group)
            total_charged = Invoice.objects.filter(student__in=students).aggregate(total=Sum("amount"))["total"] or 0
            total_paid = Payment.objects.filter(student__in=students, status="approved").aggregate(total=Sum("amount"))["total"] or 0
            pending_count = Payment.objects.filter(student__in=students, status="pending").count()
            data.append({
                "id": group.id,
                "name": group.name,
                "student_count": students.count(),
                "total_charged": float(total_charged),
                "total_paid": float(total_paid),
                "total_debt": float(total_charged) - float(total_paid),
                "pending_payments": pending_count,
            })
        return Response(data)


class AccountantGroupStudentsAPIView(APIView):
    """List all students in a group with their invoice/payment status."""
    permission_classes = [IsAccountant]

    def get(self, request, group_id):
        students = Student.objects.filter(group_id=group_id)
        data = []
        for student in students:
            invoices = Invoice.objects.filter(student=student)
            total_charged = invoices.aggregate(total=Sum("amount"))["total"] or 0
            total_paid = Payment.objects.filter(student=student, status="approved").aggregate(total=Sum("amount"))["total"] or 0
            pending_payments = Payment.objects.filter(student=student, status="pending").count()
            invoice_list = []
            for inv in invoices:
                invoice_list.append({
                    "id": inv.id,
                    "title": inv.title,
                    "amount": float(inv.amount),
                    "status": inv.status,
                    "due_date": str(inv.due_date),
                    "total_paid": float(inv.total_paid),
                })
            data.append({
                "student_id": student.id,
                "student_name": student.get_full_name(),
                "total_charged": float(total_charged),
                "total_paid": float(total_paid),
                "debt": float(total_charged) - float(total_paid),
                "pending_payments": pending_payments,
                "invoices": invoice_list,
            })
        return Response(data)


class AccountantCreateGroupInvoicesAPIView(APIView):
    """Bulk create invoices for all students in a group."""
    permission_classes = [IsAccountant]

    def post(self, request, group_id):
        title = request.data.get("title", "Tuition Fee")
        amount = request.data.get("amount")
        due_date = request.data.get("due_date")

        if not amount or not due_date:
            return Response({"detail": "amount and due_date are required."}, status=400)

        students = Student.objects.filter(group_id=group_id)
        if not students.exists():
            return Response({"detail": "No students in this group."}, status=404)

        created = 0
        for student in students:
            invoice = Invoice.objects.create(
                student=student,
                title=title,
                amount=amount,
                due_date=due_date,
                status="pending",
                admin=request.user if request.user.is_superuser else None
            )
            # Notify student
            Notification.objects.create(
                recipient=student.student,
                sender=request.user,
                title=f"New Invoice: {title}",
                message=f"You have a new invoice of {amount} due by {due_date}.",
                notification_type="warning"
            )
            # Notify parents
            from accounts.models import Parent
            for parent in Parent.objects.filter(student=student):
                Notification.objects.create(
                    recipient=parent.user,
                    sender=request.user,
                    title=f"Invoice for {student.get_full_name()}",
                    message=f"New invoice: {title} — {amount}. Due: {due_date}.",
                    notification_type="warning"
                )
            created += 1

        return Response({"status": "success", "invoices_created": created})


class AccountantPendingPaymentsAPIView(generics.ListAPIView):
    serializer_class = PaymentListSerializer
    permission_classes = [IsAccountant]

    def get_queryset(self):
        return Payment.objects.filter(status="pending").select_related("student", "invoice")


class AccountantVerifyPaymentAPIView(APIView):
    permission_classes = [IsAccountant]

    def post(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk)
            new_status = request.data.get("status")
            if new_status not in ["approved", "rejected"]:
                return Response({"detail": "Invalid status."}, status=400)

            payment.status = new_status
            payment.accountant = request.user
            payment.save()
            payment.invoice.update_status()

            Notification.objects.create(
                recipient=payment.student.student,
                sender=request.user,
                title=f"Payment {new_status.capitalize()}",
                message=f"Your payment of {payment.amount} for «{payment.invoice.title}» has been {new_status}.",
                notification_type="success" if new_status == "approved" else "warning"
            )
            # Notify parents too
            from accounts.models import Parent
            for parent in Parent.objects.filter(student=payment.student):
                Notification.objects.create(
                    recipient=parent.user,
                    sender=request.user,
                    title=f"Payment {new_status.capitalize()} — {payment.student.get_full_name()}",
                    message=f"Payment of {payment.amount} for «{payment.invoice.title}» has been {new_status} by accountant.",
                    notification_type="success" if new_status == "approved" else "warning"
                )

            return Response({"status": "success", "new_status": new_status})
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=404)


class AccountantSendDebtNotificationAPIView(APIView):
    permission_classes = [IsAccountant]

    def post(self, request):
        student_id = request.data.get("student_id")
        amount = request.data.get("amount")
        deadline = request.data.get("deadline")
        message_text = request.data.get("message", f"You have an outstanding debt of {amount}. Please pay by {deadline}.")

        try:
            student = Student.objects.get(pk=student_id)
            Notification.objects.create(
                recipient=student.student,
                sender=request.user,
                title="⚠️ Debt Notification",
                message=message_text,
                notification_type="warning"
            )
            from accounts.models import Parent
            for parent in Parent.objects.filter(student=student):
                Notification.objects.create(
                    recipient=parent.user,
                    sender=request.user,
                    title=f"⚠️ Debt: {student.get_full_name()}",
                    message=message_text,
                    notification_type="warning"
                )
            return Response({"status": "notifications_sent"})
        except Student.DoesNotExist:
            return Response({"detail": "Student not found."}, status=404)


# ===================== Parent: Upload Receipt =====================

class ParentUploadReceiptAPIView(generics.CreateAPIView):
    serializer_class = PaymentWriteSerializer
    permission_classes = [IsStudentOrParent]

    def perform_create(self, serializer):
        serializer.save(status="pending")


class AccountantBalanceListAPIView(generics.ListAPIView):
    serializer_class = StudentBalanceSerializer
    permission_classes = [IsAccountant]

    def get_queryset(self):
        # This is a bit of a hack since StudentBalanceSerializer is a Serializer, not ModelSerializer
        # We'll handle the data in list()
        return Student.objects.all()

    def list(self, request, *args, **kwargs):
        students = Student.objects.all()
        data = []
        for student in students:
            total_charged = Invoice.objects.filter(student=student).aggregate(total=Sum("amount"))["total"] or 0
            total_paid = Payment.objects.filter(student=student, status="approved").aggregate(total=Sum("amount"))["total"] or 0
            data.append({
                "student_id": student.pk,
                "student_name": student.get_full_name(),
                "total_charged": float(total_charged),
                "total_paid": float(total_paid),
                "balance": float(total_charged) - float(total_paid),
            })
        return Response(data)

class AccountantPendingPaymentsAPIView(generics.ListAPIView):
    serializer_class = PaymentListSerializer
    permission_classes = [IsAccountant]

    def get_queryset(self):
        return Payment.objects.filter(status="pending")

class AccountantVerifyPaymentAPIView(APIView):
    permission_classes = [IsAccountant]

    def post(self, request, pk):
        try:
            payment = Payment.objects.get(pk=pk)
            status = request.data.get("status") # "approved" or "rejected"
            if status not in ["approved", "rejected"]:
                return Response({"detail": "Invalid status."}, status=400)
            
            payment.status = status
            payment.accountant = request.user
            payment.save()
            payment.invoice.update_status()

            # Notify user
            Notification.objects.create(
                recipient=payment.student.student,
                sender=request.user,
                title=f"Payment {status.capitalize()}",
                message=f"Your payment of {payment.amount} for {payment.invoice.title} has been {status}.",
                notification_type="success" if status == "approved" else "warning"
            )

            return Response({"status": "success", "new_status": status})
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=404)

class AccountantSendDebtNotificationAPIView(APIView):
    permission_classes = [IsAccountant]

    def post(self, request):
        student_id = request.data.get("student_id")
        amount = request.data.get("amount")
        deadline = request.data.get("deadline")
        
        try:
            student = Student.objects.get(pk=student_id)
            # Notify student
            Notification.objects.create(
                recipient=student.student,
                sender=request.user,
                title="Debt Notification",
                message=f"You have an outstanding debt of {amount}. Please pay by {deadline}.",
                notification_type="warning"
            )
            # Notify parents
            from accounts.models import Parent
            parents = Parent.objects.filter(student=student)
            for parent in parents:
                Notification.objects.create(
                    recipient=parent.user,
                    sender=request.user,
                    title=f"Debt Notification for {student.get_full_name()}",
                    message=f"Your child has an outstanding debt of {amount}. Please pay by {deadline}.",
                    notification_type="warning"
                )
            return Response({"status": "notifications_sent"})
        except Student.DoesNotExist:
            return Response({"detail": "Student not found."}, status=404)

# ===================== Parent: Upload Receipt =====================

class ParentUploadReceiptAPIView(generics.CreateAPIView):
    serializer_class = PaymentWriteSerializer
    permission_classes = [IsStudentOrParent]

    def perform_create(self, serializer):
        serializer.save(status="pending")

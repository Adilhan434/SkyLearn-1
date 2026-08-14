# Audit model for Release 1

## Purpose

New Release 1 domain models inherit `audit.models.AuditModel`. It is an
abstract Django model and therefore does not create its own database table.
It provides a consistent minimum audit contract:

- `created_at` is set when an object is created;
- `updated_at` is refreshed when an object is saved;
- `created_by` identifies the user who created the object;
- `updated_by` identifies the user responsible for the latest change.

`created_by` and `updated_by` are nullable and use `SET_NULL`. Deleting a user
must not delete Organization or Course records. Nullable values also allow
data migrations, imports and automated system operations that have no acting
user.

This shared mechanism records ownership and timestamps only.

`audit.CourseHistoryEvent` is the append-only course-scoped event store used by
the Release 1 history API. It stores the acting user plus a snapshot of the
affected object's type, ID and title, so delete events remain readable after
the original Module, Topic, Lesson or Material has been removed. The optional
`details` JSON object contains action-specific context; it must not contain
secrets or complete field-level snapshots.

The older `courses.CourseStatusHistory` model remains available while
lifecycle writers are migrated to the common event store.

## Using the model

```python
from audit.models import AuditModel


class Example(AuditModel):
    name = models.CharField(max_length=255)
```

The current Release 1 models in `organization` and `courses` already inherit
this base class.

## API writes

The authenticated user must be assigned explicitly in the serializer or
service that performs the write:

```python
def create(self, validated_data):
    user = self.context["request"].user
    return Example.objects.create(
        created_by=user,
        updated_by=user,
        **validated_data,
    )
```

For an update, assign `updated_by` before saving. Do not accept either audit
user field directly from an untrusted request body.

## Django Admin

Admin classes for audited models inherit `audit.admin.AuditAdminMixin`. It
sets `created_by` on the first save, refreshes `updated_by` on every Admin
save, and exposes all audit fields as read-only values.

## Seeds, imports and migrations

Management commands should provide a known service/admin user when one is
available. Data migrations may leave the user fields null. Never create a
fake user only to satisfy audit fields.

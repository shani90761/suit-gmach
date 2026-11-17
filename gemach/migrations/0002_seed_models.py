from django.db import migrations


def seed(apps, schema_editor):
    M = apps.get_model("gemach", "JacketModel")
    for i, name in enumerate(["קטיפה שחורה", "שמנת"]):
        M.objects.get_or_create(name=name, defaults={"order": i})


class Migration(migrations.Migration):
    dependencies = [("gemach", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
